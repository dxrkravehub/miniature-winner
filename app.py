import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import io
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

# Импорты модулей проекта
from analysis import normalize_defects, compute_inspection_summary, compare_with_previous
from csv_parser import parse_inspection_csv
from report import build_report_context, generate_report_texts
from docx_template import fill_template_docx, create_blank_template
from scheme_generator import (
    assign_scheme_coordinates, create_scheme_image, 
    get_defect_at_position, find_nearest_infrastructure
)
from defect_explainer import explain_defect_location, generate_defect_explanation

# Настройка страницы
st.set_page_config(
    page_title="Мониторинг трубопроводов",
    page_icon="🔧",
    layout="wide"
)

st.title("🔧 Система мониторинга трубопроводов")

# Сайдбар
with st.sidebar:
    st.header("📂 Загрузка данных")
    
    # Загрузка Excel
    excel_file = st.file_uploader(
        "Загрузите Excel с аномалиями",
        type=['xlsx', 'xls'],
        help="Файл должен содержать лист 'Аномалии подлежащие ремонту'"
    )
    
    # Загрузка CSV (опциональная - только если нужны доп. метаданные)
    csv_file = st.file_uploader(
        "Загрузите CSV с координатами (опционально)",
        type=['csv'],
        help="Файл с результатами магнитной дефектоскопии (необязательно, если координаты есть в Excel)"
    )
    
    # Опциональная загрузка предыдущей инспекции
    st.divider()

# Проверка загрузки файлов
if not excel_file:
    st.info("👆 Загрузите Excel файл для начала работы")
    st.stop()

# Обработка данных
try:
    # Читаем Excel - только лист "Аномалии подлежащие ремонту"
    with st.spinner("Загрузка Excel..."):
        excel_data = pd.ExcelFile(excel_file)
        sheet_name = "Аномалии подлежащие ремонту"
        
        if sheet_name not in excel_data.sheet_names:
            st.error(f"❌ Лист '{sheet_name}' не найден в Excel файле")
            st.info(f"Доступные листы: {', '.join(excel_data.sheet_names)}")
            st.stop()
        
        df_raw = pd.read_excel(excel_file, sheet_name=sheet_name)
        defects_df = normalize_defects(df_raw)
        st.success(f"✅ Загружено {len(defects_df)} дефектов")
    
    # Извлекаем метаданные из Excel или используем значения по умолчанию
    inspection_meta = {
        'pipeline_name': 'Основной трубопровод',
        'diameter_mm': 530,
        'segment_km': '0-15',
        'method': 'Магнитоскан (MFL)',
        'start_date': None,
        'end_date': None
    }
    
    # Извлекаем координаты из Excel (если есть)
    coords_df = pd.DataFrame()
    if 'latitude' in defects_df.columns and 'longitude' in defects_df.columns:
        coords_df = defects_df[['latitude', 'longitude', 'elevation_m', 
                                 'anomaly_type', 'measured_distance_m']].copy()
        coords_df = coords_df.dropna(subset=['latitude', 'longitude'])
        st.success(f"✅ Найдено {len(coords_df)} точек с координатами в Excel")
    
    # Читаем CSV только если он загружен (для дополнительных метаданных)
    if csv_file:
        with st.spinner("Загрузка CSV..."):
            temp_csv_path = "temp_coords.csv"
            with open(temp_csv_path, 'wb') as f:
                f.write(csv_file.getvalue())
            
            try:
                csv_meta, csv_coords = parse_inspection_csv(temp_csv_path)
                # Обновляем метаданные из CSV
                inspection_meta.update(csv_meta)
                st.success(f"✅ Метаданные обновлены из CSV")
            except Exception as csv_error:
                st.warning(f"⚠️ Не удалось прочитать CSV: {str(csv_error)}")
                st.info("Продолжаем работу с данными из Excel")
    
    # Вычисляем текущую статистику
    current_summary = compute_inspection_summary(defects_df, inspection_meta)
    
    # Присваиваем координаты на схеме и классифицируем по инфраструктуре
    defects_with_coords = assign_scheme_coordinates(current_summary['table'])
    current_summary['table'] = defects_with_coords
    
    # Обработка предыдущей инспекции
    previous_summary = None
    delta = None

except Exception as e:
    st.error(f"❌ Ошибка при обработке файлов: {str(e)}")
    st.exception(e)
    st.stop()

# === СХЕМА ТРУБОПРОВОДА С ДЕФЕКТАМИ ===
st.subheader("🔧 Схема трубопровода и анализ дефектов")

col_scheme, col_analysis = st.columns([2, 1])

with col_scheme:
    # Проверяем наличие scheme.png
    if not os.path.exists("scheme.png"):
        st.warning("⚠️ Файл scheme.png не найден!")
        st.info("""
        Пожалуйста, поместите файл **scheme.png** в корень проекта.
        
        Это должна быть реальная схема трубопровода (чертёж/фото).
        
        Система будет рисовать дефекты ПОВЕРХ этой схемы.
        """)
    else:
        st.success("✅ Базовая схема scheme.png найдена")
    
    # Генерируем схему с дефектами
    if st.button("🎨 Нарисовать дефекты на схеме", type="primary"):
        with st.spinner("Рисуем дефекты на scheme.png..."):
            try:
                scheme_path = create_scheme_image(
                    defects_with_coords, 
                    base_scheme_path="scheme.png",
                    output_path="scheme_with_defects.png"
                )
                st.success("✅ Схема с дефектами создана!")
                st.session_state['scheme_generated'] = True
                st.session_state['scheme_path'] = scheme_path
            except FileNotFoundError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Ошибка при создании схемы: {str(e)}")
    
    # Отображаем схему если она создана
    if st.session_state.get('scheme_generated', False):
        scheme_path = st.session_state.get('scheme_path', 'scheme_with_defects.png')
        if os.path.exists(scheme_path):
            st.image(scheme_path, caption="Схема с отмеченными дефектами", use_column_width=True)
            
            # Информация о инфраструктуре
            with st.expander("ℹ️ Обозначения на схеме"):
                st.markdown("""
                **Объекты инфраструктуры:**
                - 🔵 **Синий квадрат (ВП)** - Байпас (678, 243)
                - 🟢 **Зелёный круг (З)** - Задвижки
                  - Задвижка 1: (563, 349)
                  - Задвижка 2: (393, 191)
                  - Задвижка 3: (569, 113)
                
                **Дефекты:**
                - 🔴 Красная точка - Высокий риск
                - 🟠 Оранжевая точка - Средний риск
                - 🟢 Зелёная точка - Низкий риск
                
                Координаты указаны в пикселях на изображении.
                """)
        else:
            st.warning(f"Файл {scheme_path} не найден")

with col_analysis:
    st.write("**Анализ по объектам инфраструктуры**")
    
    # Группировка дефектов по близости к объектам
    infrastructure_groups = {}
    for idx, row in defects_with_coords.iterrows():
        location = row.get('infrastructure_location', 'неизвестно')
        if location not in infrastructure_groups:
            infrastructure_groups[location] = 0
        infrastructure_groups[location] += 1
    
    # Отображаем статистику
    for location, count in infrastructure_groups.items():
        st.metric(location, count)

st.divider()

# === ИНТЕРАКТИВНЫЙ АНАЛИЗ ДЕФЕКТОВ ===
st.subheader("🔍 Интерактивный анализ дефектов")

col_select, col_analyze = st.columns([1, 1])

with col_select:
    # Выбор дефекта для анализа
    defect_ids = defects_with_coords['identification'].dropna().tolist()
    if not defect_ids:
        defect_ids = [f"DEF-{i+1}" for i in range(len(defects_with_coords))]
    
    selected_defect_id = st.selectbox(
        "Выберите дефект для детального анализа:",
        options=defect_ids,
        help="Выберите дефект, чтобы получить объяснение через AI"
    )

with col_analyze:
    analyze_button = st.button("🤖 Проанализировать дефект", type="primary", use_container_width=True)

if selected_defect_id and analyze_button:
    with st.spinner("Анализ дефекта через Gemini AI..."):
        try:
            # Находим дефект
            if 'identification' in defects_with_coords.columns:
                defect_row = defects_with_coords[
                    defects_with_coords['identification'] == selected_defect_id
                ].iloc[0].to_dict()
            else:
                idx = int(selected_defect_id.split('-')[1]) - 1
                defect_row = defects_with_coords.iloc[idx].to_dict()
            
            # Отображаем параметры дефекта
            st.markdown("### 📊 Параметры дефекта:")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("ID", selected_defect_id)
                st.metric("Тип", defect_row.get('anomaly_type', 'N/A'))
                st.metric("Глубина, %", f"{defect_row.get('depth_pct', 'N/A')}")
            
            with col2:
                st.metric("ERF B31G", f"{defect_row.get('erf_b31g', 'N/A')}")
                st.metric("ERF DNV", f"{defect_row.get('erf_dnv', 'N/A')}")
                st.metric("Класс риска", defect_row.get('risk_class', 'N/A'))
            
            with col3:
                st.metric("Остат. ТС, мм", f"{defect_row.get('wall_thickness_remaining_mm', 'N/A')}")
                st.metric("Локация", defect_row.get('surface_location', 'N/A'))
                st.metric("Ремонт", defect_row.get('repair_flag', 'N/A'))
            
            st.divider()
            
            # Получаем объяснение от LLM
            st.markdown("### 🤖 Анализ от Gemini AI:")
            explanation = generate_defect_explanation(defect_row)
            st.info(explanation)
            
            st.divider()
            
            # Анализ связи с инфраструктурой
            infrastructure_loc = defect_row.get('infrastructure_location', 'неизвестно')
            distance = defect_row.get('distance_to_infrastructure', 999)
            
            st.markdown("### 🏗️ Связь с инфраструктурой:")
            
            col_inf1, col_inf2 = st.columns(2)
            with col_inf1:
                st.metric("Ближайший объект", infrastructure_loc)
            with col_inf2:
                st.metric("Расстояние", f"{distance:.1f} пикселей")
            
            if infrastructure_loc != 'удаленный участок трубопровода':
                st.markdown("**Вопрос AI:** *Связан ли этот дефект с объектом инфраструктуры?*")
                location_analysis = explain_defect_location(defect_row, infrastructure_loc)
                st.warning(location_analysis)
            else:
                st.info("Дефект находится на удалённом участке трубопровода, вдали от байпассов и задвижек.")
        
        except Exception as e:
            st.error(f"Ошибка при анализе: {str(e)}")
            st.exception(e)

st.divider()
st.subheader("Сравнение с прошлой инспекцией")
previous_excel = st.file_uploader(
    "Загрузите прошлый Excel (опционально)",
    type=['xlsx', 'xls'],
    key='previous'
)

if previous_excel:
    with st.spinner("Обработка предыдущей инспекции..."):
        prev_data = pd.ExcelFile(previous_excel)
        sheet_name = "Аномалии подлежащие ремонту"
        if sheet_name in prev_data.sheet_names:
            df_prev_raw = pd.read_excel(previous_excel, sheet_name=sheet_name)
            df_prev = normalize_defects(df_prev_raw)
            previous_summary = compute_inspection_summary(df_prev, inspection_meta)
            delta = compare_with_previous(current_summary, previous_summary)

st.divider()
st.caption("Разработано для хакатона")

# === ОСНОВНОЙ ЭКРАН ===

# KPI карточки
st.header("📊 Ключевые показатели")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Активные дефекты",
        current_summary['overview']['total_defects'],
        delta=delta['defects_change'] if delta else None
    )

with col2:
    st.metric(
        "Высокий риск",
        current_summary['by_risk']['High'],
        delta=delta['high_risk_change'] if delta else None,
        delta_color="inverse"
    )

with col3:
    st.metric(
        "Обследования",
        2 if previous_summary else 1
    )

with col4:
    repairs_count = sum(1 for flag in current_summary['by_repair_flag'].keys() 
                       if 'ремонт' in str(flag).lower())
    st.metric(
        "Требуют ремонта",
        current_summary['by_risk']['High'] + current_summary['by_risk']['Medium']
    )

st.divider()

# Фильтры и визуализация
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("🗺️ Карта трассы трубопровода")
    
    # Используем координаты из Excel
    if len(coords_df) > 0:
        # Создаём карту с Plotly
        fig_map = px.scatter_mapbox(
            coords_df,
            lat='latitude',
            lon='longitude',
            hover_name='anomaly_type',
            hover_data=['measured_distance_m', 'elevation_m'],
            color='anomaly_type',
            zoom=10,
            height=500,
            title=f"Обнаружено {len(coords_df)} дефектов с координатами"
        )
        
        fig_map.update_layout(
            mapbox_style="open-street-map",
            margin={"r": 0, "t": 30, "l": 0, "b": 0}
        )
        
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.info("🔍 Координаты не найдены в Excel. Убедитесь, что есть колонки 'Широта [°]' и 'Долгота [°]'")

with col_right:
    st.subheader("🎯 Распределение по риску")
    
    risk_data = pd.DataFrame({
        'Класс риска': ['Высокий', 'Средний', 'Низкий'],
        'Количество': [
            current_summary['by_risk']['High'],
            current_summary['by_risk']['Medium'],
            current_summary['by_risk']['Low']
        ]
    })
    
    fig_pie = px.pie(
        risk_data,
        values='Количество',
        names='Класс риска',
        color='Класс риска',
        color_discrete_map={
            'Высокий': '#ff4444',
            'Средний': '#ffaa00',
            'Низкий': '#44ff44'
        }
    )
    
    st.plotly_chart(fig_pie, use_container_width=True)

st.divider()

# Фильтры
st.subheader("🔎 Фильтры")
col_f1, col_f2, col_f3 = st.columns(3)

with col_f1:
    risk_filter = st.multiselect(
        "Класс риска",
        options=['High', 'Medium', 'Low'],
        default=['High', 'Medium', 'Low']
    )

with col_f2:
    if 'anomaly_type' in current_summary['table'].columns:
        anomaly_types = current_summary['table']['anomaly_type'].dropna().unique()
        type_filter = st.multiselect(
            "Тип аномалии",
            options=anomaly_types,
            default=anomaly_types
        )
    else:
        type_filter = []

with col_f3:
    st.write(f"**Трубопровод:** {inspection_meta['pipeline_name']}")
    st.write(f"**Участок:** {inspection_meta['segment_km']} км")

# Таблица дефектов
st.subheader("📋 Реестр дефектов")

# Фильтруем данные
filtered_df = current_summary['table'][
    current_summary['table']['risk_class'].isin(risk_filter)
]

if type_filter and 'anomaly_type' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['anomaly_type'].isin(type_filter)]

# Выбираем колонки для отображения
display_cols = ['section_id', 'anomaly_type', 'risk_class', 'repair_flag', 
                'depth_pct', 'erf_b31g', 'wall_thickness_remaining_mm', 'repair_priority']

display_cols = [col for col in display_cols if col in filtered_df.columns]

# Функция для подсветки рисков
def highlight_risk(row):
    if row['risk_class'] == 'High':
        return ['background-color: #ffcccc'] * len(row)
    elif row['risk_class'] == 'Medium':
        return ['background-color: #fff4cc'] * len(row)
    else:
        return ['background-color: #ccffcc'] * len(row)

styled_df = filtered_df[display_cols].style.apply(highlight_risk, axis=1)

st.dataframe(styled_df, use_container_width=True, height=400)

st.divider()

# События
st.subheader("📢 События и уведомления")

events = []

# Событие о новых аномалиях высокого риска
if current_summary['by_risk']['High'] > 0:
    events.append({
        'type': '🚨',
        'message': f"Обнаружено {current_summary['by_risk']['High']} аномалий высокого риска, требующих немедленного внимания"
    })

# Сравнение с предыдущей инспекцией
if delta and delta.get('has_previous'):
    if delta['defects_change'] > 0:
        events.append({
            'type': '📈',
            'message': f"Количество дефектов увеличилось на {delta['defects_change']} ({delta['defects_change_pct']}%)"
        })
    elif delta['defects_change'] < 0:
        events.append({
            'type': '📉',
            'message': f"Количество дефектов уменьшилось на {abs(delta['defects_change'])} ({abs(delta['defects_change_pct'])}%)"
        })

if not events:
    events.append({
        'type': 'ℹ️',
        'message': "Данные успешно загружены и проанализированы"
    })

for event in events:
    st.info(f"{event['type']} {event['message']}")

st.divider()

# Генерация отчёта
st.subheader("📄 Генерация отчёта")

col_rep1, col_rep2 = st.columns([3, 1])

with col_rep1:
    st.write("Сформируйте Word-отчёт по результатам обследования с использованием AI-анализа")

with col_rep2:
    # Проверяем наличие template.docx
    if not os.path.exists("template.docx"):
        st.warning("⚠️ template.docx не найден")
        if st.button("📝 Создать базовый шаблон"):
            create_blank_template("template.docx")
            st.success("✅ Создан template.docx")
            st.info("Теперь отредактируйте его, добавив логотипы и печати!")
            st.rerun()
    
    if st.button("🤖 Сформировать отчёт", type="primary", use_container_width=True):
        with st.spinner("Генерация отчёта через Gemini AI..."):
            try:
                # Проверяем наличие файлов
                if not os.path.exists("template.docx"):
                    st.error("❌ template.docx не найден! Создайте его сначала.")
                    st.stop()
                
                # Собираем контекст
                context = build_report_context(current_summary, previous_summary, 
                                              inspection_meta, delta)
                
                # Генерируем тексты через LLM
                texts = generate_report_texts(context)
                
                # Проверяем наличие схемы с дефектами
                scheme_path = st.session_state.get('scheme_path', 'scheme_with_defects.png')
                if not os.path.exists(scheme_path):
                    st.warning("Схема не создана, создаём автоматически...")
                    if os.path.exists("scheme.png"):
                        scheme_path = create_scheme_image(
                            defects_with_coords, 
                            base_scheme_path="scheme.png",
                            output_path="scheme_with_defects.png"
                        )
                    else:
                        st.warning("scheme.png не найден, отчёт будет без схемы")
                        scheme_path = None
                
                # Заполняем шаблон
                output_path = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
                fill_template_docx(
                    template_path="template.docx",
                    context=context,
                    texts=texts,
                    scheme_image_path=scheme_path,
                    output_path=output_path
                )
                
                # Читаем для скачивания
                with open(output_path, 'rb') as f:
                    docx_bytes = f.read()
                
                # Кнопка для скачивания
                st.download_button(
                    label="📥 Скачать отчёт (DOCX)",
                    data=docx_bytes,
                    file_name=output_path,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
                
                st.success("✅ Отчёт успешно сформирован!")
                
            except FileNotFoundError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"❌ Ошибка при генерации отчёта: {str(e)}")
                st.exception(e)

st.divider()

# Q&A секция
with st.expander("💬 Задать вопрос по отчёту (Q&A)", expanded=False):
    st.write("**Задайте любой вопрос AI-ассистенту о текущем состоянии трубопровода**")
    st.caption("Примеры: 'Какие дефекты требуют первоочередного ремонта?', 'Почему возникают дефекты у задвижек?', 'Какова общая ситуация?'")
    
    question = st.text_area(
        "Ваш вопрос:", 
        placeholder="Например: Какие дефекты находятся рядом с байпасом и насколько они опасны?",
        height=100
    )
    
    col_q1, col_q2 = st.columns([3, 1])
    
    with col_q2:
        ask_button = st.button("🤖 Спросить", type="primary", use_container_width=True)
    
    if ask_button and question:
        with st.spinner("Обработка вопроса через Gemini AI..."):
            from llm_client import call_llm, get_system_prompt
            
            context = build_report_context(current_summary, previous_summary, 
                                         inspection_meta, delta)
            
            # Добавляем информацию о группировке по инфраструктуре
            infrastructure_groups = {}
            for idx, row in defects_with_coords.iterrows():
                location = row.get('infrastructure_location', 'неизвестно')
                if location not in infrastructure_groups:
                    infrastructure_groups[location] = []
                infrastructure_groups[location].append({
                    'id': row.get('identification', f'DEF-{idx}'),
                    'type': row.get('anomaly_type', 'N/A'),
                    'risk': row.get('risk_class', 'N/A'),
                    'depth': row.get('depth_pct', 'N/A')
                })
            
            context['infrastructure_groups'] = infrastructure_groups
            
            system_prompt = get_system_prompt()
            answer = call_llm(system_prompt, question, context)
            
            st.markdown("### 🤖 Ответ ассистента:")
            st.success(answer)
    
    elif ask_button:
        st.warning("⚠️ Пожалуйста, введите вопрос")