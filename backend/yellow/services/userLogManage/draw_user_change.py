# Private iCAP Yellow business implementation. Do not publish.
import matplotlib.pyplot as plt
from datetime import datetime
raw_data = '\n1-10: 3\n1-12: 27\n1-13: 28\n1-14: 30\n1-15: 21\n1-16: 2\n1-17: 3\n1-19: 6\n1-20: 35\n1-21: 2\n1-22: 14\n1-23: 36\n1-24: 4\n1-26: 10\n1-27: 13\n1-28: 37\n1-29: 30\n1-30: 15\n1-31: 17\n1-4: 11\n1-5: 19\n1-6: 2\n1-8: 8\n1-9: 67\n2-10: 47\n2-11: 26\n2-12: 52\n2-13: 21\n2-14: 8\n2-2: 25\n2-24: 6\n2-25: 11\n2-26: 40\n2-27: 7\n2-28: 9\n2-3: 68\n2-4: 29\n2-5: 25\n2-6: 17\n2-7: 3\n2-9: 16\n3-1: 1\n3-10: 16\n3-11: 26\n3-12: 10\n3-13: 7\n3-14: 4\n3-16: 38\n3-17: 48\n3-18: 29\n3-19: 10\n3-2: 18\n3-20: 9\n3-23: 22\n3-24: 10\n3-25: 28\n3-26: 3\n3-27: 8\n3-28: 19\n3-3: 21\n3-30: 30\n3-31: 68\n3-4: 5\n3-5: 14\n3-6: 20\n3-7: 2\n3-9: 18\n4-1: 22\n4-10: 5\n4-13: 3\n4-14: 2\n4-15: 1\n4-16: 14\n4-17: 14\n4-2: 14\n4-20: 22\n4-21: 4\n4-22: 10\n4-23: 14\n4-24: 3\n4-25: 14\n4-27: 3\n4-28: 2\n4-29: 3\n4-3: 11\n4-30: 13\n4-7: 19\n4-8: 4\n4-9: 6\n5-11: 42\n5-12: 11\n5-13: 1\n5-14: 7\n5-15: 1\n5-17: 1\n5-18: 42\n5-19: 15\n5-20: 506\n5-21: 344\n5-22: 705\n5-25: 17\n5-26: 20\n5-27: 65\n5-28: 28\n5-29: 3\n5-30: 4\n5-6: 1\n5-7: 3\n5-8: 8\n5-9: 24\n6-1: 37\n6-10: 4\n6-11: 2\n6-15: 3\n6-16: 6\n6-17: 2\n6-2: 4\n6-20: 9\n6-23: 2\n6-24: 9\n6-25: 2\n6-26: 2\n6-27: 4\n6-28: 1\n6-29: 10\n6-3: 14\n6-30: 9\n6-4: 15\n6-5: 9\n6-6: 15\n6-8: 10\n6-9: 3\n'
data_list = []
for line in raw_data.strip().split('\n'):
    if line.strip():
        date_str, value_str = line.split(':')
        month, day = map(int, date_str.strip().split('-'))
        year = 2025 if month == 12 else 2026
        dt = datetime(year, month, day)
        data_list.append((dt, int(value_str.strip()), date_str.strip()))
data_list.sort(key=lambda x: x[0])
dates = [item[2] for item in data_list]
values = [item[1] for item in data_list]
from collections import defaultdict
print('===== 每日平均值 =====')
daily_groups = defaultdict(list)
for dt, val, date_str in data_list:
    daily_groups[date_str].append(val)
for date_str in sorted(daily_groups.keys(), key=lambda d: (int(d.split('-')[0]), int(d.split('-')[1]))):
    vals = daily_groups[date_str]
    avg = sum(vals) / len(vals)
    print(f'{date_str}: {avg:.2f}')
print('\n===== 每周平均值 =====')
weekly_groups = defaultdict(list)
for dt, val, date_str in data_list:
    year_week = f'{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}'
    weekly_groups[year_week].append(val)
for week in sorted(weekly_groups.keys()):
    vals = weekly_groups[week]
    avg = sum(vals) / len(vals)
    print(f'{week}: {avg:.2f}')
print('\n===== 每月平均值 =====')
monthly_groups = defaultdict(list)
for dt, val, date_str in data_list:
    year_month = dt.strftime('%Y-%m')
    monthly_groups[year_month].append(val)
for month in sorted(monthly_groups.keys()):
    vals = monthly_groups[month]
    avg = sum(vals) / len(vals)
    print(f'{month}: {avg:.2f}')
plt.figure(figsize=(12, 6))
plt.plot(dates, values, marker='o', linestyle='-', color='b', linewidth=2, markersize=6)
n = len(values)
show_indices = set()
if n > 100:
    for group_start in range(0, n, 3):
        group_end = min(group_start + 3, n)
        forced_indices = [i for i in range(group_start, group_end) if values[i] > 50]
        if forced_indices:
            show_indices.update(forced_indices)
        else:
            best_idx = max(range(group_start, group_end), key=lambda i: values[i])
            show_indices.add(best_idx)
else:
    show_indices = set(range(n))
for i, val in enumerate(values):
    if i in show_indices:
        plt.text(i, val + 3, str(val), ha='center', va='bottom', fontsize=9)
ax = plt.gca()
ax.set_xticks(range(n))
xtick_labels = [dates[i] if i in show_indices else '' for i in range(n)]
ax.set_xticklabels(xtick_labels, rotation=45)
plt.title('Daily Data Trend', fontsize=14)
plt.xlabel('Date (Month-Day)', fontsize=12)
plt.ylabel('Value', fontsize=12)
plt.grid(True, linestyle='--', alpha=0.6)
plt.tight_layout()
plt.show()
