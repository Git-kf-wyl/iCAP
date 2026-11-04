# Private iCAP Yellow business implementation. Do not publish.
import os
import jsonlines as jsonl

class DumpMode:
    OVERWRITE = 'overwrite'
    APPEND = 'append'

def dump_jsonl_data(data_list, jsonl_file, dump_mode=DumpMode.OVERWRITE):
    """
    Dump data to jsonl file.

    Args:
        data_list: data list to be dumped.  [{'a': 'aaa'}, ...]
        jsonl_file: jsonl file path.
        dump_mode: dump mode. It can be 'overwrite' or 'append'.
    """
    if not jsonl_file:
        raise ValueError('output file must be provided.')
    jsonl_file = os.path.expanduser(jsonl_file)
    if not isinstance(data_list, list):
        data_list = [data_list]
    if dump_mode == DumpMode.OVERWRITE:
        dump_mode = 'w'
    elif dump_mode == DumpMode.APPEND:
        dump_mode = 'a'
    with jsonl.open(jsonl_file, mode=dump_mode) as writer:
        writer.write_all(data_list)
