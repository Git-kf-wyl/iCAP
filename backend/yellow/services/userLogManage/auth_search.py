# Private iCAP Yellow business implementation. Do not publish.
import ldap3
import pandas as pd
from typing import List, Dict, Any
import os

def login_ldap(username, password, search_name=None):
    LDAP_AUTH_URL = 'http://127.0.0.1:1/unconfigured'
    if search_name is not None:
        value = search_name
    else:
        value = username
    attr_list = ['hw-DepartName1', 'hw-DepartName2', 'hw-DepartName3', 'hw-DepartName4', 'hw-DepartName5', 'hw-DepartName6', 'extensionAttribute1', 'givenName', 'mobile', 'mail', 'samaccountname', 'displayname', 'title']
    search_filter = '(&(|(cn=' + value + '*)(givenName=' + value + '*)(mail=' + value + '*)(sn=' + value + '*)(samAccountName=' + value + '*)(name=' + value + '*))(!(objectClass=computer))(!(objectClass=contact)))'
    base = 'dc=china,dc=huawei,dc=com'
    try:
        server = ldap3.Server(LDAP_AUTH_URL, use_ssl=False, get_info=ldap3.ALL)
        conn = ldap3.Connection(server, auto_bind=True, client_strategy=ldap3.SYNC, user='china\\' + username, password=password, authentication=ldap3.SIMPLE)
        conn.search(base, search_filter, attributes=attr_list)
        for entry in conn.entries:
            if entry is not None:
                return entry
    except Exception as e:
        print(e)
    return None

def process_txt_to_excel(txt_file_path: str, output_excel_path: str) -> None:
    """
    读取txt文件，处理每一行并调用指定函数，将结果写入Excel

    Args:
        txt_file_path: 输入的txt文件路径
        output_excel_path: 输出的Excel文件路径
        your_function: 你要提供的函数，接收三个参数，返回字典
    """
    print(f'正在读取文件: {txt_file_path}')
    try:
        with open(txt_file_path, 'r', encoding='utf-8') as file:
            lines = [line.strip() for line in file if line.strip()]
        seen = set()
        unique_lines = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                unique_lines.append(line)
        print(f'读取完成，共有 {len(lines)} 行，去重后剩余 {len(unique_lines)} 行')
    except FileNotFoundError:
        print(f'错误：找不到文件 {txt_file_path}')
        return
    except Exception as e:
        print(f'读取文件时出错：{e}')
        return
    results_data = []
    print('开始处理数据...')
    for i, element in enumerate(unique_lines, 1):
        if 'element' == 'admin':
            element = 'w00649384'
        try:
            result_dict = login_ldap('w00649384', 'season97@@', element)
            name = str(result_dict['extensionAttribute1'])
            dept4 = str(result_dict['hw-DepartName4'])
            dept5 = str(result_dict['hw-DepartName5'])
            dept6 = str(result_dict['hw-DepartName6'])
            results_data.append({'工号': element, '姓名': name, '四级部门': dept4, '五级部门': dept5, '六级部门': dept6})
            if i % 100 == 0:
                print(f'已处理 {i}/{len(unique_lines)} 行')
        except Exception as e:
            print(f"处理元素 '{element}' 时出错：{e}")
            results_data.append({'工号': element, '姓名': '', '四级部门': '', '五级部门': '', '六级部门': ''})
    print('正在写入Excel文件...')
    df = pd.DataFrame(results_data)
    try:
        os.makedirs(os.path.dirname(output_excel_path) if os.path.dirname(output_excel_path) else '.', exist_ok=True)
        df.to_excel(output_excel_path, index=False, engine='openpyxl')
        print(f'成功写入Excel文件: {output_excel_path}')
        print(f'总共处理了 {len(results_data)} 条记录')
    except Exception as e:
        print(f'写入Excel文件时出错：{e}')
        csv_path = output_excel_path.replace('.xlsx', '.csv')
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        print(f'已保存为CSV文件: {csv_path}')
