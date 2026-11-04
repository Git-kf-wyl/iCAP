# Private iCAP Yellow implementation. Do not publish.
import multiprocessing
from typing import Optional, Dict, Any, List
import contextlib
import faulthandler
import io
import os
import platform
import signal
import tempfile
import threading
import ctypes
IS_WINDOWS = platform.system() == 'Windows'

def unsafe_execute(problem: Dict[str, Any], completion: str, timeout: float, result: List):
    """Runs untrusted code in a sandboxed environment."""
    with create_tempdir():
        import os
        import shutil
        rmtree = shutil.rmtree
        rmdir = os.rmdir
        chdir = os.chdir
        reliability_guard()
        check_program = problem['prompt'] + completion + '\n' + problem['test'] + '\n' + f"check({problem['entry_point']})"
        try:
            exec_globals = {}
            with swallow_io():
                with time_limit(timeout):
                    exec(check_program, exec_globals)
            result.append('passed')
        except TimeoutException:
            result.append('timed out')
        except BaseException as e:
            result.append(f'failed: {e}')
        shutil.rmtree = rmtree
        os.rmdir = rmdir
        os.chdir = chdir

def check_correctness(problem: Dict, completion: str, timeout: float, completion_id: Optional[int]=None) -> Dict:
    """
    Evaluates the functional correctness of a completion by running the test
    suite provided in the problem.
    """
    manager = multiprocessing.Manager()
    result = manager.list()
    if IS_WINDOWS:
        ctx = multiprocessing.get_context('spawn')
        with ctx.Pool(processes=1) as pool:
            async_result = pool.apply_async(unsafe_execute, args=(problem, completion, timeout, result))
            try:
                async_result.get(timeout=timeout + 1)
            except multiprocessing.TimeoutError:
                result.append('timed out')
                pool.terminate()
                pool.join()
    else:
        p = multiprocessing.Process(target=unsafe_execute, args=(problem, completion, timeout, result))
        p.start()
        p.join(timeout=timeout + 1)
        if p.is_alive():
            p.terminate()
            p.join()
    if not result:
        result.append('timed out')
    return dict(task_id=problem['task_id'], passed=result[0] == 'passed', result=result[0], completion_id=completion_id)

def _windows_time_limit(seconds: float):
    """Windows-specific timeout implementation using threading."""
    done = threading.Event()
    raised = threading.Event()
    target_thread_id = threading.current_thread().ident

    def timeout_function():
        if not done.is_set() and target_thread_id:
            raised.set()
            ctypes.pythonapi.PyThreadState_SetAsyncExc(target_thread_id, ctypes.py_object(TimeoutException))
    timer = threading.Timer(seconds, timeout_function)
    timer.start()
    try:
        yield
    finally:
        done.set()
        timer.cancel()
        timer.join()
        if raised.is_set():
            ctypes.pythonapi.PyThreadState_SetAsyncExc(target_thread_id, None)

def _unix_time_limit(seconds: float):
    """Unix-specific timeout implementation using SIGALRM."""

    def signal_handler(signum, frame):
        raise TimeoutException('Timed out!')
    old_handler = signal.signal(signal.SIGALRM, signal_handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)

@contextlib.contextmanager
def time_limit(seconds: float):
    """Cross-platform timeout context manager."""
    if IS_WINDOWS:
        yield from _windows_time_limit(seconds)
    else:
        yield from _unix_time_limit(seconds)

@contextlib.contextmanager
def swallow_io():
    stream = WriteOnlyStringIO()
    with contextlib.redirect_stdout(stream):
        with contextlib.redirect_stderr(stream):
            with redirect_stdin(stream):
                yield

@contextlib.contextmanager
def create_tempdir():
    with tempfile.TemporaryDirectory() as dirname:
        with chdir(dirname):
            yield dirname

class TimeoutException(Exception):
    pass

class WriteOnlyStringIO(io.StringIO):
    """StringIO that throws an exception when it's read from"""

    def read(self, *args, **kwargs):
        raise IOError

    def readline(self, *args, **kwargs):
        raise IOError

    def readlines(self, *args, **kwargs):
        raise IOError

    def readable(self, *args, **kwargs):
        """Returns True if the IO object can be read."""
        return False

class redirect_stdin(contextlib._RedirectStream):
    _stream = 'stdin'

@contextlib.contextmanager
def chdir(root):
    if root == '.':
        yield
        return
    cwd = os.getcwd()
    os.chdir(root)
    try:
        yield
    except BaseException as exc:
        raise exc
    finally:
        os.chdir(cwd)

def reliability_guard(maximum_memory_bytes: Optional[int]=None):
    """
    This disables various destructive functions and prevents the generated code
    from interfering with the test (e.g. fork bomb, killing other processes,
    removing filesystem files, etc.)
    WARNING
    This function is NOT a security sandbox. Untrusted code, including, model-
    generated code, should not be blindly executed outside of one. See the
    generated code, should not be blindly executed outside of one. See the
    Codex paper for more information about OpenAI's code sandbox, and proceed
    with caution.
    """
    if maximum_memory_bytes is not None:
        if not IS_WINDOWS:
            try:
                import resource
                resource.setrlimit(resource.RLIMIT_AS, (maximum_memory_bytes, maximum_memory_bytes))
                resource.setrlimit(resource.RLIMIT_DATA, (maximum_memory_bytes, maximum_memory_bytes))
                if not platform.uname().system == 'Darwin':
                    resource.setrlimit(resource.RLIMIT_STACK, (maximum_memory_bytes, maximum_memory_bytes))
            except ImportError:
                pass
        else:
            import win32job
            import win32api
            job = win32job.CreateJobObject(None, '')
            process = win32api.GetCurrentProcess()
            info = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
            info['BasicLimitInformation']['LimitFlags'] |= win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY
            info['ProcessMemoryLimit'] = maximum_memory_bytes
            win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, info)
            win32job.AssignProcessToJobObject(job, process)
    faulthandler.disable()
    import builtins
    builtins.exit = None
    builtins.quit = None
    import os
    os.environ['OMP_NUM_THREADS'] = '1'
    os.kill = None
    os.system = None
    os.putenv = None
    os.remove = None
    os.removedirs = None
    os.rmdir = None
    os.fchdir = None
    os.setuid = None
    os.fork = None
    os.forkpty = None
    os.killpg = None
    os.rename = None
    os.renames = None
    os.truncate = None
    os.replace = None
    os.unlink = None
    os.fchmod = None
    os.fchown = None
    os.chmod = None
    os.chown = None
    os.chroot = None
    os.fchdir = None
    os.lchflags = None
    os.lchmod = None
    os.lchown = None
    os.getcwd = None
    os.chdir = None
    import shutil
    shutil.rmtree = None
    shutil.move = None
    shutil.chown = None
    import subprocess
    subprocess.Popen = None
    __builtins__['help'] = None
    import sys
    sys.modules['ipdb'] = None
    sys.modules['joblib'] = None
    sys.modules['resource'] = None
    sys.modules['psutil'] = None
    sys.modules['tkinter'] = None
