# Private iCAP Yellow business implementation. Do not publish.
from services.aisf.clarify.Book.Version.testBook import run_book
from services.aisf.clarify.Hotel.Version.testHotel import run_hotel
from services.aisf.clarify.ShopFood_normal.Version_KnowledgeBase.testfood import run_food
from services.aisf.clarify.ShopFood_normal.Version_KnowledgeBase.testshop import run_shop
from services.aisf.clarify.Taxi.Version.testTaxi import run_taxi
from services.aisf.clarify.Trip.Version.testTrip import run_trip
from services.aisf.clarify.clarify_util import merge_summary
from services.aisf.clarify.constants import CLARIFY_BASE_DIR_OUTPUT
from services.aisf.zip_util import zip_directory
from utils.consts import AISF_RESULT_FILE, AISF_ERR_RESULT_FILE
test_model_name = 'Qwen3-32B'
test_model_url = 'http://127.0.0.1:1/unconfigured'

def run_all_scenes(task_id, model_name: str, model_url: str):
    print(f'run_all_scenes: {task_id}, {model_name}, {model_url}')
    run_book(task_id, model_name, model_url)
    run_hotel(task_id, model_name, model_url)
    run_food(task_id, model_name, model_url)
    run_shop(task_id, model_name, model_url)
    run_taxi(task_id, model_name, model_url)
    run_trip(task_id, model_name, model_url)
    try:
        merge_summary(CLARIFY_BASE_DIR_OUTPUT + task_id, CLARIFY_BASE_DIR_OUTPUT + task_id)
        zip_directory(CLARIFY_BASE_DIR_OUTPUT + task_id, CLARIFY_BASE_DIR_OUTPUT + task_id + AISF_RESULT_FILE)
        zip_directory(CLARIFY_BASE_DIR_OUTPUT + task_id, CLARIFY_BASE_DIR_OUTPUT + task_id + AISF_ERR_RESULT_FILE, True)
    except BaseException as e:
        print(f'合并表格或者压缩失败！{e}')
