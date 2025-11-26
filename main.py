# 文件名: mobile_app_safe_v25_6.py
# 版本: V25.6 
# 修复: 解决了 AttributeError: module 'flet' has no attribute 'icons' / 'colors'
# 改动: 将所有 ft.icons.XXX 和 ft.colors.XXX 替换为纯字符串 (如 "person" 代替 ft.icons.PERSON)，确保在任何环境下都能运行。

import os
# --- 关键配置 ---
os.environ["HOME"] = "/tmp"

import flet as ft
import pandas as pd
import calendar
import traceback
import uuid
from datetime import datetime
from collections import defaultdict

# =============================================================================
# 全局配色与样式配置 (One UI 风格)
# =============================================================================
class AppTheme:
    # 字体配置
    FONT_FAMILY = "Microsoft YaHei, PingFang SC, Segoe UI, sans-serif"
    
    # 基础色调 (全部使用 Hex 字符串)
    BG_COLOR = "#F8F9FA"        # 极淡的灰白背景
    SURFACE_COLOR = "#FFFFFF"   # 卡片白色背景
    TEXT_PRIMARY = "#2C3E50"    # 深灰主文字
    TEXT_SECONDARY = "#7F8C8D"  # 浅灰次要文字
    PRIMARY_BTN = "#5D6D7E"     # 按钮主色 (低饱和蓝灰)

    # 班次颜色 (低饱和度莫兰迪色系)
    COLOR_JINJIANG = "#E6B0AA"  # 柔和红/粉 (锦江)
    COLOR_JIAKUAI = "#D98880"   # 稍深的柔和红 (加快)
    COLOR_CAITU = "#A9CCE3"     # 柔和蓝 (采图)
    COLOR_JILU = "#A3E4D7"      # 柔和青 (记录)
    COLOR_QUCAI = "#F9E79F"     # 柔和黄 (取材)
    COLOR_DEFAULT = "#AED6F1"   # 默认柔和蓝 (普通班)
    
    # 样式常量
    CARD_RADIUS = 24            # 大圆角
    BTN_RADIUS = 30             # 胶囊按钮
    BORDER_COLOR = "#EBEDEF"    # 极浅边框

# =============================================================================
# 核心逻辑层 (保持不变)
# =============================================================================
class ScheduleEngine:
    def __init__(self):
        self.schedule_data = None
        self.granular_schedule_data = None
        self.selected_year = str(datetime.now().year)
    
    def _get_date_info(self, date_val, day_val=None):
        if pd.isna(date_val) or str(date_val).strip() == '': return None, None
        year_str = self.selected_year
        if not year_str.isdigit() or len(year_str) != 4: return None, None
        ts = None
        try:
            if isinstance(date_val, (int, float)):
                ts = pd.to_datetime(date_val, unit='D', origin='1899-12-30')
            else:
                ts = pd.to_datetime(date_val)
        except:
            try:
                date_str = str(date_val).split(' ')[0]
                ts = pd.to_datetime(f"{year_str}-{date_str}")
            except:
                return None, None
        if ts is not None:
            if str(ts.year) != year_str: return None, None
            try:
                date_obj = ts.to_pydatetime()
                day_of_week = str(day_val) if day_val and not pd.isna(day_val) else date_obj.strftime('%A')
                return date_obj, day_of_week
            except:
                return None, None
        return None, None

    def _handle_special_shifts(self, all_entries):
        standard_weekdays = {"一", "二", "三", "四", "五", "六", "日"}
        special_shift_dates = set()
        for entry in all_entries:
            if not entry: continue
            day_str = str(entry.get('day')).strip()
            if day_str and day_str not in standard_weekdays:
                special_shift_dates.add(entry['date_obj'].date())
        if not special_shift_dates: return all_entries
        final_entries = []
        for entry in all_entries:
            if not entry: continue
            entry_date = entry['date_obj'].date()
            day_str = str(entry.get('day')).strip()
            is_special = day_str and day_str not in standard_weekdays
            if entry_date in special_shift_dates:
                if is_special:
                    entry['time_of_day'] = "晚上"
                    original_activity = entry.get('activity', '')
                    base = original_activity.replace('上午', '').replace('下午', '')
                    entry['activity'] = "加强" + (base or '')
                    final_entries.append(entry)
            else:
                final_entries.append(entry)
        return final_entries

    def _process_value_match(self, value, name):
        if isinstance(value, str):
            cleaned_value = "".join(value.split())
            return name in cleaned_value
        return False

    def parse_files(self, filepaths, name_to_find, year_str):
        self.selected_year = year_str
        all_entries = []
        name_clean = "".join(name_to_find.split())
        
        for f in filepaths:
            try:
                xls = pd.ExcelFile(f)
                for sheet_name in xls.sheet_names:
                    df = None
                    identifier = sheet_name.lower()
                    if '锦江' in identifier:
                        df = pd.read_excel(xls, sheet_name=sheet_name, header=[1, 2])
                        all_entries.extend(self._parse_multilevel_df(df, name_clean, "锦江分院"))
                    elif any(x in identifier for x in ['采图', '加快', '专科会诊']):
                        df = pd.read_excel(xls, sheet_name=sheet_name, header=1)
                        all_entries.extend(self._parse_special_shifts_df(df, name_clean))
                    else:
                        try:
                            df = pd.read_excel(xls, sheet_name=sheet_name, header=[1, 2, 3])
                        except:
                            try:
                                df = pd.read_excel(xls, sheet_name=sheet_name, header=1)
                                continue
                            except:
                                continue
                        if not isinstance(df.columns, pd.MultiIndex) or df.columns.nlevels < 3: continue
                        header_level_2 = df.columns.get_level_values(1)
                        if '上午' in header_level_2 or '下午' in header_level_2:
                            all_entries.extend(self._parse_multilevel_df(df, name_clean, "总院区"))
                        else:
                            all_entries.extend(self._parse_waijian_df(df, name_clean))
            except Exception as e:
                print(f"Error parsing {f}: {e}")
                continue

        unique_entries = []
        seen_keys = set()
        for entry in all_entries:
            key = (entry['date_obj'].date(), entry['location'], entry['time_of_day'])
            if key not in seen_keys:
                seen_keys.add(key)
                unique_entries.append(entry)
        all_entries = unique_entries

        final_entries = self._handle_special_shifts(all_entries)
        final_entries.sort(key=lambda x: x['date_obj'])
        self.granular_schedule_data = final_entries
        return final_entries

    def _parse_waijian_df(self, df, name):
        entries = []
        for index, row in df.iterrows():
            date_obj, day_of_week = self._get_date_info(row.iloc[0], row.iloc[1])
            if not date_obj: continue
            for col_tuple, value in row.items():
                if self._process_value_match(value, name):
                    details = [str(c).strip() for c in col_tuple if pd.notna(c) and 'Unnamed' not in str(c) and str(c).strip()]
                    if not details: continue
                    activity = " ".join(details)
                    location = "总院区"
                    if any(loc in activity for loc in ['天府', '上锦', '永宁']):
                        if '天府' in activity: location = '天府院区'
                        elif '上锦' in activity: location = '上锦院区'
                        elif '永宁' in activity: location = '永宁院区'
                    elif '快速初诊' in activity:
                        location = '加快'
                        activity = activity.replace('快速初诊', '加快') 
                    if activity:
                        entries.append({'date_obj': date_obj, 'day': day_of_week, 'time_of_day': '全天', 'activity': activity, 'location': location})
        return entries

    def _parse_multilevel_df(self, df, name, location):
        entries = []
        for index, row in df.iterrows():
            date_obj, day_of_week = self._get_date_info(row.iloc[0], row.iloc[1])
            if not date_obj: continue
            for col_tuple, value in row.items():
                if self._process_value_match(value, name):
                    details = [str(c).strip() for c in col_tuple if pd.notna(c) and 'Unnamed' not in str(c) and str(c).strip()]
                    if not details: continue
                    activity, time_of_day = '', '全天'
                    if location == '锦江分院':
                        task = details[0] if len(details) > 0 else ''; group = details[1] if len(details) > 1 else ''; activity = f"{group}{task}" if group else task
                    else:
                        task = details[0] if len(details) > 0 else ''; time_of_day = details[1] if len(details) > 1 else '全天'
                        if '上' in time_of_day and '午' not in time_of_day: time_of_day = '上午'
                        elif '下' in time_of_day and '午' not in time_of_day: time_of_day = '下午'
                        group = details[2] if len(details) > 2 else ''; activity = f"{group}{task}" if group else task
                    entries.append({'date_obj': date_obj, 'day': day_of_week, 'time_of_day': time_of_day, 'activity': activity, 'location': location})
        return entries
        
    def _parse_special_shifts_df(self, df, name):
        entries = []
        for index, row in df.iterrows():
            date_obj, day_of_week = self._get_date_info(row.get('日期'), row.get('星期'))
            if not date_obj: continue
            for col, value in row.items():
                if self._process_value_match(value, name):
                    col_name = str(col).strip(); activity, location = '', ''
                    if '采图' in col_name: activity, location = '采图', '采图与找片子'
                    elif '血液' in col_name: activity, location = '血液会诊', '采图与找片子'
                    elif '消化' in col_name: activity, location = '消化会诊', '采图与找片子'
                    elif col_name not in ['日期', '星期'] and 'Unnamed' not in col_name:
                        location = '加快'; activity = f"加快 ({col_name})"
                    if activity and location:
                        entries.append({'date_obj': date_obj, 'day': day_of_week, 'time_of_day': '全天', 'activity': activity, 'location': location})
        return entries

    def calculate_stats(self, all_entries):
        imaging_shifts = 0; qucai_shifts = 0; jilu_shifts = 0; jiakuai_shifts = 0; total_shifts = 0
        for entry in all_entries:
            if not entry: continue
            increment = 2 if entry.get('location') == '锦江分院' else 1
            total_shifts += increment
            activity = entry.get('activity', ''); location = entry.get('location', '')
            if '取材' in activity: qucai_shifts += increment
            elif '记录' in activity: jilu_shifts += increment
            elif location == '加快': jiakuai_shifts += increment
            elif location == '采图与找片子': imaging_shifts += increment
        return {"total": total_shifts, "qucai": qucai_shifts, "jilu": jilu_shifts, "jiakuai": jiakuai_shifts, "imaging": imaging_shifts}

    def fold_line(self, line: str) -> str:
        crlf_space = '\r\n '
        line_bytes = line.encode('utf-8'); limit = 75
        if len(line_bytes) <= limit: return line
        folded_lines = []; bytes_to_process = line_bytes
        while len(bytes_to_process) > 0:
            current_limit = limit if not folded_lines else limit - 1
            if len(bytes_to_process) <= current_limit: folded_lines.append(bytes_to_process.decode('utf-8')); break
            split_pos = current_limit
            while split_pos > 0:
                try: bytes_to_process[:split_pos].decode('utf-8'); break
                except UnicodeDecodeError: split_pos -= 1
            if split_pos == 0: folded_lines.append(bytes_to_process.decode('utf-8', errors='ignore')); break
            folded_lines.append(bytes_to_process[:split_pos].decode('utf-8'))
            bytes_to_process = bytes_to_process[split_pos:]
        return folded_lines.pop(0) + crlf_space.join(folded_lines) if folded_lines else ''

    def _escape_ics_text(self, text):
        if text is None: return ''
        return str(text).replace('\\', '\\\\').replace(',', '\\,').replace(';', '\\;').replace('\n', '\\n')

    def create_ics_file(self, name, filepath):
        crlf = '\r\n'
        prodid_line = self.fold_line(f'PRODID:-//ScheduleApp//V23.0//{name}//CN')
        ics_lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', prodid_line, 'CALSCALE:GREGORIAN']
        for item in self.granular_schedule_data:
            if not item: continue
            dtstamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
            date_part = item['date_obj'].strftime('%Y%m%d')
            uid = f"{uuid.uuid4()}@scheduleapp.local"
            activity = item.get('activity', ''); time_of_day = item.get('time_of_day', ''); location = item.get('location', '')
            if location == '总院区' and time_of_day not in ['全天', '晚上']: summary_text = f"{time_of_day}{activity}"
            else: summary_text = activity
            summary = self._escape_ics_text(summary_text); location_text = self._escape_ics_text(location)
            ics_lines.append('BEGIN:VEVENT'); ics_lines.append(f'UID:{uid}'); ics_lines.append(f'DTSTAMP:{dtstamp}')
            if time_of_day == '上午': ics_lines.append(f'DTSTART:{date_part}T090000'); ics_lines.append(f'DTEND:{date_part}T120000'); description = self._escape_ics_text("班次: 上午")
            elif time_of_day == '下午': ics_lines.append(f'DTSTART:{date_part}T140000'); ics_lines.append(f'DTEND:{date_part}T170000'); description = self._escape_ics_text("班次: 下午")
            elif time_of_day == '晚上': ics_lines.append(f'DTSTART:{date_part}T190000'); ics_lines.append(f'DTEND:{date_part}T210000'); description = self._escape_ics_text("班次: 晚上 (加强)")
            else: ics_lines.append(f'DTSTART;VALUE=DATE:{date_part}'); description = self._escape_ics_text("班次: 全天")
            ics_lines.append(self.fold_line(f'SUMMARY:{summary}')); ics_lines.append(self.fold_line(f'LOCATION:{location_text}')); ics_lines.append(self.fold_line(f'DESCRIPTION:{description}')); ics_lines.append('END:VEVENT')
        ics_lines.append('END:VCALENDAR')
        with open(filepath, 'w', encoding='utf-8', newline='') as f: f.write(crlf.join(ics_lines))
        return True

# =============================================================================
# 界面层 (Flet) - 可视化日历实现
# =============================================================================
def generate_calendar_controls(entries):
    """
    根据排班数据，生成可视化的月历 Grid 组件列表
    """
    if not entries:
        return []

    data_by_month = defaultdict(lambda: defaultdict(list))
    for entry in entries:
        dt = entry['date_obj']
        key = (dt.year, dt.month)
        data_by_month[key][dt.day].append(entry)

    sorted_months = sorted(data_by_month.keys())
    calendar_controls = []

    for year, month in sorted_months:
        cal = calendar.Calendar(firstweekday=0)
        month_days = cal.monthdayscalendar(year, month)

        # 月份标题 - 现代化大字体
        month_header = ft.Container(
            content=ft.Text(f"{year}年 {month}月", size=22, weight="bold", color=AppTheme.TEXT_PRIMARY),
            alignment=ft.alignment.center_left,
            padding=ft.padding.only(left=10, bottom=10, top=10)
        )
        
        weekdays = ["一", "二", "三", "四", "五", "六", "日"]
        header_row = ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text(day, weight="normal", size=13, color=AppTheme.TEXT_SECONDARY), 
                    expand=1, 
                    alignment=ft.alignment.center
                ) for day in weekdays
            ],
            spacing=0
        )

        grid_rows = []
        for week in month_days:
            row_controls = []
            for day in week:
                if day == 0:
                    cell = ft.Container(
                        expand=1,
                        height=90,
                        bgcolor="transparent" # 修复：使用字符串 "transparent"
                    )
                else:
                    day_entries = data_by_month[(year, month)].get(day, [])
                    content_col = ft.Column(spacing=3, alignment="start", controls=[])
                    
                    # 日期数字
                    content_col.controls.append(
                        ft.Container(
                            content=ft.Text(str(day), size=14, weight="bold", color=AppTheme.TEXT_PRIMARY),
                            alignment=ft.alignment.center,
                            padding=ft.padding.only(bottom=2)
                        )
                    )

                    for entry in day_entries:
                        loc = entry['location']
                        act = entry['activity']
                        time_od = entry['time_of_day']
                        
                        # --- 核心逻辑：颜色与下方统计完全对应 ---
                        bg_color = AppTheme.COLOR_DEFAULT
                        text_color = "#333333" # 莫兰迪色背景配深灰字更清晰
                        
                        if "锦江" in loc:
                            bg_color = AppTheme.COLOR_JINJIANG
                        elif "加快" in loc:
                            bg_color = AppTheme.COLOR_JIAKUAI
                            text_color = "white" # 稍深的红色配白字
                        elif "采图" in loc:
                            bg_color = AppTheme.COLOR_CAITU
                        elif "取材" in act: # 增加取材判断
                            bg_color = AppTheme.COLOR_QUCAI
                        elif "记录" in act: # 增加记录判断
                             bg_color = AppTheme.COLOR_JILU
                        else:
                            # 普通
                            if time_od in ["上午", "下午"]:
                                act = f"{time_od[0]}{act}"

                        display_text = act[:5] + ".." if len(act) > 5 else act
                        
                        badge = ft.Container(
                            content=ft.Text(display_text, size=10, color=text_color, text_align="center", weight="w500"),
                            bgcolor=bg_color,
                            border_radius=4,
                            padding=ft.padding.symmetric(vertical=2, horizontal=4),
                            alignment=ft.alignment.center,
                            width=float("inf") # 撑满单元格宽度
                        )
                        content_col.controls.append(badge)

                    cell = ft.Container(
                        content=content_col,
                        expand=1,
                        height=90,
                        border=ft.border.all(0.5, AppTheme.BORDER_COLOR), # 极浅边框
                        bgcolor=AppTheme.SURFACE_COLOR,
                        padding=5,
                        border_radius=8 # 单元格微圆角
                    )
                row_controls.append(cell)
            
            grid_rows.append(ft.Row(controls=row_controls, spacing=4)) # 行间距

        month_card = ft.Container(
            content=ft.Column([
                month_header,
                header_row,
                ft.Divider(height=10, color="transparent"),
                ft.Column(grid_rows, spacing=4)
            ]),
            padding=20,
            bgcolor=AppTheme.SURFACE_COLOR,
            border_radius=AppTheme.CARD_RADIUS,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=15,
                color="#0D000000", # 修复：使用 Hex 字符串代替 ft.colors.with_opacity
                offset=ft.Offset(0, 4)
            )
        )
        calendar_controls.append(month_card)

    return calendar_controls

# =============================================================================
# 主界面构建 (UI 重构)
# =============================================================================
def main(page: ft.Page):
    page.title = "排班助手 "
    page.theme_mode = "light"
    page.window_width = 480 
    page.window_height = 900
    page.scroll = "hidden" # 隐藏主滚动条，使用 Column 滚动
    page.padding = 0 # 全屏布局
    page.bgcolor = AppTheme.BG_COLOR
    page.fonts = {"AppFont": AppTheme.FONT_FAMILY}
    page.theme = ft.Theme(font_family="AppFont")
    
    engine = ScheduleEngine()
    uploaded_files = []

    def show_msg(msg, color=AppTheme.TEXT_PRIMARY):
        page.snack_bar = ft.SnackBar(
            ft.Text(msg, color="white"), 
            bgcolor="#34495E", 
            behavior=ft.SnackBarBehavior.FLOATING,
            margin=ft.margin.all(20)
        )
        page.snack_bar.open = True
        page.update()

    # --- UI 组件封装 ---
    
    # 标题栏
    header = ft.Container(
        content=ft.Column([
            ft.Text("排班助手", size=28, weight="bold", color=AppTheme.TEXT_PRIMARY),
            ft.Text("V25.6 ", size=14, color=AppTheme.TEXT_SECONDARY),
        ], spacing=5),
        padding=ft.padding.only(top=50, left=25, right=25, bottom=20),
    )

    # 输入区域
    name_input = ft.TextField(
        label="姓名", 
        hint_text="输入你的名字",
        prefix_icon="person_outline", # 修复：使用字符串
        border_color="transparent",
        bgcolor="white",
        text_size=16,
        border_radius=15,
        content_padding=20,
        expand=True,
        text_style=ft.TextStyle(color=AppTheme.TEXT_PRIMARY)
    )
    
    year_input = ft.TextField(
        label="年份", 
        value=str(datetime.now().year), 
        prefix_icon="calendar_today_outlined", # 修复：使用字符串
        border_color="transparent",
        bgcolor="white",
        text_size=16,
        border_radius=15,
        content_padding=20,
        width=130,
        keyboard_type="number",
        text_style=ft.TextStyle(color=AppTheme.TEXT_PRIMARY)
    )
    
    file_status_text = ft.Text("请先上传 Excel 排班表", size=13, color=AppTheme.TEXT_SECONDARY)

    def on_file_picked(e: ft.FilePickerResultEvent):
        if e.files:
            uploaded_files.clear()
            names = []
            for f in e.files:
                uploaded_files.append(f.path)
                names.append(f.name)
            file_status_text.value = f"已就绪: {len(names)} 个文件"
            file_status_text.color = AppTheme.PRIMARY_BTN
            show_msg(f"已加载 {len(names)} 个文件")
        else:
            file_status_text.value = "未选择文件"
        page.update()

    file_picker = ft.FilePicker(on_result=on_file_picked)
    page.overlay.append(file_picker)
    
    # 大按钮样式
    def create_big_btn(text, icon_name, on_click, bgcolor=AppTheme.PRIMARY_BTN, disabled=False):
        return ft.ElevatedButton(
            text=text,
            icon=icon_name, # 传入字符串
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=AppTheme.BTN_RADIUS),
                padding=20,
                bgcolor={"": bgcolor, "disabled": "#D6DBDF"},
                color="white",
                elevation=0,
            ),
            width=1000, # fill width
            on_click=on_click,
            disabled=disabled
        )

    btn_upload = create_big_btn("上传排班表", "upload_file_rounded", lambda _: file_picker.pick_files(allow_multiple=True, allowed_extensions=["xls", "xlsx"]), bgcolor="#5D6D7E")

    # 结果容器
    stats_container = ft.Container()
    calendar_view_container = ft.Column(spacing=20)

    # 导出逻辑
    def save_ics_result(e: ft.FilePickerResultEvent):
        if e.path:
            try:
                engine.create_ics_file(name_input.value, e.path)
                show_msg("日历文件已保存")
            except Exception as err:
                show_msg(f"失败: {err}")
    
    ics_picker = ft.FilePicker(on_result=save_ics_result)
    page.overlay.append(ics_picker)

    btn_export_ics = create_big_btn("保存到手机日历 (.ics)", "save_alt_rounded", lambda _: ics_picker.save_file(dialog_title="保存ICS", file_name=f"{name_input.value}_排班.ics"), disabled=True, bgcolor=AppTheme.PRIMARY_BTN)


    def generate_click(e):
        name = name_input.value.strip()
        year = year_input.value.strip()
        
        if not uploaded_files:
            show_msg("请先上传文件")
            return
        if not name:
            show_msg("请输入姓名")
            return
        
        btn_generate.disabled = True
        btn_generate.text = "正在计算..."
        page.update()
        
        try:
            entries = engine.parse_files(uploaded_files, name, year)
            
            stats_container.content = None
            calendar_view_container.controls.clear()

            if not entries:
                calendar_view_container.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Icon("error_outline", size=50, color="#E57373"),
                            ft.Text(f"未找到 '{name}' 的排班数据", color=AppTheme.TEXT_SECONDARY)
                        ], horizontal_alignment="center"),
                        alignment=ft.alignment.center, 
                        padding=40
                    )
                )
                btn_export_ics.disabled = True
            else:
                stats = engine.calculate_stats(entries)
                btn_export_ics.disabled = False
                
                # --- 统计卡片 (One UI 风格) ---
                def create_stat_chip(label, count, color, text_color="#333333"):
                    return ft.Container(
                        content=ft.Row([
                            ft.Container(width=8, height=8, bgcolor=color, border_radius=4),
                            ft.Text(f"{label} {count}", size=12, color=text_color, weight="bold")
                        ], spacing=5, alignment="center"),
                        bgcolor="white",
                        border=ft.border.all(1, "#F0F0F0"),
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                        border_radius=12
                    )

                stats_container.content = ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text("总班数", size=14, color=AppTheme.TEXT_SECONDARY),
                            ft.Text(str(stats['total']), size=32, weight="bold", color=AppTheme.TEXT_PRIMARY)
                        ], alignment="spaceBetween", vertical_alignment="center"),
                        ft.Divider(height=20, color="transparent"),
                        ft.Row([
                            create_stat_chip("取材", stats['qucai'], AppTheme.COLOR_QUCAI),
                            create_stat_chip("记录", stats['jilu'], AppTheme.COLOR_JILU),
                            create_stat_chip("加快", stats['jiakuai'], AppTheme.COLOR_JIAKUAI, text_color="#D98880"),
                            create_stat_chip("采图", stats['imaging'], AppTheme.COLOR_CAITU),
                        ], wrap=True, spacing=10, run_spacing=10)
                    ]),
                    padding=25, 
                    bgcolor=AppTheme.SURFACE_COLOR, 
                    border_radius=AppTheme.CARD_RADIUS,
                    shadow=ft.BoxShadow(spread_radius=0, blur_radius=15, color="#0D000000") # 修复 Hex 颜色
                )

                cal_controls = generate_calendar_controls(entries)
                calendar_view_container.controls.extend(cal_controls)
                
                show_msg(f"计算完成，共 {len(entries)} 条")

        except Exception as err:
            show_msg(f"错误: {str(err)}")
            print(traceback.format_exc())
        finally:
            btn_generate.disabled = False
            btn_generate.text = "生成排班视图"
            page.update()

    btn_generate = create_big_btn("生成排班视图", "auto_awesome_rounded", generate_click, bgcolor="#3498DB")

    # 主滚动容器
    main_scroll = ft.Column([
        header,
        ft.Container(
            content=ft.Column([
                # 上传区
                ft.Container(
                    content=ft.Column([
                        btn_upload,
                        ft.Container(file_status_text, alignment=ft.alignment.center),
                    ]),
                    padding=0
                ),
                ft.Divider(height=10, color="transparent"),
                # 输入区
                ft.Row([name_input, year_input], spacing=15),
                ft.Divider(height=10, color="transparent"),
                # 动作区
                btn_generate,
                ft.Divider(height=20, color="transparent"),
                # 结果区
                stats_container,
                ft.Divider(height=20, color="transparent"),
                calendar_view_container,
                ft.Divider(height=20, color="transparent"),
                btn_export_ics,
                ft.Divider(height=30, color="transparent"),
            ]),
            padding=ft.padding.symmetric(horizontal=25)
        )
    ], scroll="auto", expand=True)

    page.add(main_scroll)

if __name__ == "__main__":
    ft.app(target=main)