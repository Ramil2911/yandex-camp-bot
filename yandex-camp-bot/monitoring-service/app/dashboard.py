import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import socket
from typing import Dict, List, Any

# Настройки
MONITORING_SERVICE_URL = "http://localhost:8004"
REFRESH_INTERVAL = 30  # секунды

st.set_page_config(
    page_title="YandexCamp Monitoring Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 YandexCamp Monitoring Dashboard")

# Код будет выполнен в функции main() после загрузки данных

def show_full_trace_details(full_trace: Dict[str, Any]):
    """Показать детальную информацию о полном трейсе"""
    if not full_trace:
        st.error("Нет данных для отображения")
        return

    # Отладочная информация (можно убрать в продакшене)
    with st.expander("🔍 Отладочная информация", expanded=False):
        st.write(f"Ключи в данных: {list(full_trace.keys())}")
        st.write(f"Полные данные: {full_trace}")

    st.subheader("🔍 Полный трейс запроса")

    # Основная информация
    col1, col2, col3 = st.columns(3)
    with col1:
        request_id = full_trace.get("request_id", "N/A")
        st.metric("Request ID", request_id)
    with col2:
        trace_id = full_trace.get("trace_id", "N/A")
        st.metric("Trace ID", trace_id)
    with col3:
        status = full_trace.get("status", "N/A")
        st.metric("Статус", status)

    # Время выполнения
    st.subheader("⏰ Время выполнения")
    start_time = full_trace.get("start_time")
    end_time = full_trace.get("end_time")
    duration = full_trace.get("total_duration")
    
    if start_time:
        st.write(f"**Время начала:** {start_time}")
    else:
        st.write("**Время начала:** N/A")
        
    if end_time:
        st.write(f"**Время окончания:** {end_time}")
    else:
        st.write("**Время окончания:** N/A")
        
    if duration:
        st.write(f"**Общее время выполнения:** {duration:.2f}ms")
    else:
        st.write("**Общее время выполнения:** N/A")

    # Путь через сервисы
    st.subheader("🏗️ Путь через сервисы")
    services_path = full_trace.get("services_path", [])
    st.write(f"**Количество сервисов в пути:** {len(services_path)}")
    
    if services_path:
        st.write("**Данные пути через сервисы:**")
        st.json(services_path)
        
        try:
            services_df = pd.DataFrame(services_path)
            if not services_df.empty:
                st.write("**Таблица сервисов:**")
                # Выбираем нужные колонки для отображения
                display_cols = ["service", "operation", "duration", "status"]
                available_cols = [col for col in display_cols if col in services_df.columns]
                st.write(f"Доступные колонки: {available_cols}")

                if available_cols:
                    st.dataframe(
                        services_df[available_cols],
                        use_container_width=True
                    )
                else:
                    st.write("**Все колонки:**")
                    st.dataframe(services_df, use_container_width=True)
            else:
                st.warning("DataFrame пустой")
        except Exception as e:
            st.error(f"Ошибка при создании DataFrame: {str(e)}")
    else:
        st.warning("Нет данных о пути через сервисы")

    # Timeline визуализация была удалена для упрощения интерфейса

    # Ошибки в трейсе
    errors = full_trace.get("errors", [])
    st.subheader("🚨 Детальный анализ ошибок в трейсе")
    st.write(f"**Количество ошибок в трейсе:** {len(errors)}")
    
    if errors:
        st.write("**Данные об ошибках:**")
        st.json(errors)

        # Статистика ошибок
        try:
            errors_df = pd.DataFrame(errors)
            if not errors_df.empty:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Всего ошибок в трейсе", len(errors_df))
                with col2:
                    st.metric("Сервисов с ошибками", errors_df['service'].nunique() if 'service' in errors_df.columns else 0)
                with col3:
                    st.metric("Категорий ошибок", errors_df['category'].nunique() if 'category' in errors_df.columns else 0)
                # Таблица всех ошибок в трейсе
                if not errors_df.empty:
                    st.subheader("📋 Все ошибки в трейсе")
                    try:
                        display_cols = ['timestamp', 'service', 'error_type', 'category', 'error_message']
                        available_cols = [col for col in display_cols if col in errors_df.columns]
                        
                        if available_cols:
                            st.dataframe(
                                errors_df[available_cols].head(10),
                                use_container_width=True,
                                column_config={
                                    "timestamp": st.column_config.DatetimeColumn("Время", format="DD.MM.YYYY HH:mm:ss"),
                                    "service": "Сервис",
                                    "error_type": "Тип ошибки",
                                    "category": "Категория",
                                    "error_message": st.column_config.TextColumn("Сообщение", width="large"),
                                }
                            )
                        else:
                            st.dataframe(errors_df.head(10), use_container_width=True)
                    except Exception as e:
                        st.error(f"Ошибка при отображении таблицы ошибок: {str(e)}")

                # Детальный просмотр каждой ошибки
                for i, error in enumerate(errors):
                    with st.expander(f"❌ Ошибка {i+1}: {error.get('service')} - {error.get('error_type')} - {error.get('category', 'unknown')}"):
                        # Основная информация
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**🕒 Время:** {error.get('timestamp', 'N/A')}")
                            st.write(f"**🏢 Сервис:** {error.get('service', 'N/A')}")
                            st.write(f"**⚠️ Тип ошибки:** {error.get('error_type', 'N/A')}")
                            st.write(f"**🏷️ Категория:** {error.get('category', 'N/A')}")

                        with col2:
                            st.write(f"**🆔 Trace ID:** `{error.get('trace_id', 'N/A')}`")
                            st.write(f"**📝 Request ID:** `{error.get('request_id', 'N/A')}`")

                        # Полное сообщение об ошибке
                        st.subheader("📄 Полное сообщение об ошибке")
                        message = error.get('error_message', '')
                        if len(message) > 300:
                            st.text_area(f"Сообщение ошибки {i+1}", message, height=100, disabled=True, key=f"error_msg_{i}")
                        else:
                            st.code(message, language="text")

                        # Stack trace
                        if error.get("stack_trace"):
                            with st.expander("📄 Stack Trace"):
                                st.code(error.get("stack_trace", ""), language="text")

                        # Контекст ошибки
                        if error.get("context"):
                            with st.expander("📋 Контекст ошибки"):
                                st.json(error.get("context", {}))

                        # Связанные данные
                        if error.get("user_id") or error.get("session_id"):
                            st.subheader("👤 Информация о пользователе")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Пользователь:** {error.get('user_id', 'N/A')}")
                            with col2:
                                st.write(f"**Сессия:** {error.get('session_id', 'N/A')}")
        except Exception as e:
            st.error(f"Ошибка при обработке статистики ошибок: {str(e)}")
    else:
        st.info("В этом трейсе нет ошибок")


def show_error_details(errors_data, error_category):
    """Показать детальную информацию об ошибках"""
    if not errors_data:
        st.info(f"Не удалось загрузить {error_category} ошибки")
        return

    df_errors = pd.DataFrame(errors_data)
    if df_errors.empty:
        st.info(f"Нет данных о {error_category} ошибках")
        return

    # Расширенная таблица с дополнительными колонками
    display_cols = ['timestamp', 'service', 'error_type', 'error_message', 'trace_id', 'request_id', 'user_id', 'session_id']
    available_cols = [col for col in display_cols if col in df_errors.columns]

    if available_cols:
        # Добавляем колонку с кратким сообщением для лучшей читаемости
        if 'error_message' in df_errors.columns:
            df_errors['short_message'] = df_errors['error_message'].str[:100] + '...'

        # Настраиваем отображение таблицы
        column_config = {
            "timestamp": st.column_config.DatetimeColumn("Время", format="DD.MM.YYYY HH:mm:ss"),
            "service": st.column_config.TextColumn("Сервис", width="small"),
            "error_type": st.column_config.TextColumn("Тип ошибки", width="medium"),
            "error_message": st.column_config.TextColumn("Сообщение", width="large"),
            "short_message": st.column_config.TextColumn("Сообщение", width="large"),
            "trace_id": st.column_config.TextColumn("Trace ID", width="medium"),
            "request_id": st.column_config.TextColumn("Request ID", width="medium"),
            "user_id": st.column_config.TextColumn("Пользователь", width="small"),
            "session_id": st.column_config.TextColumn("Сессия", width="small"),
        }

        # Показываем расширенную таблицу
        st.dataframe(
            df_errors[available_cols].head(10),
            use_container_width=True,
            column_config=column_config
        )

        # Детальный просмотр выбранной ошибки
        if len(df_errors) > 0:
            selected_error_idx = st.selectbox(
                f"Выберите {error_category} ошибку для детального анализа:",
                range(len(df_errors.head(10))),
                format_func=lambda x: f"{df_errors.iloc[x]['service']} - {df_errors.iloc[x]['error_type']} - {df_errors.iloc[x]['error_message'][:50]}...",
                key=f"{error_category}_error_select"
            )

            if selected_error_idx is not None:
                selected_error = df_errors.iloc[selected_error_idx]
                show_detailed_error_analysis(selected_error, error_category)


def show_detailed_security_violation(violation):
    """Показать детальный анализ нарушения безопасности"""
    with st.expander("🔍 Детальный анализ нарушения безопасности", expanded=True):
        
        # Основная информация о нарушении
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📋 Основная информация")
            st.write(f"**🕒 Время:** {violation.get('timestamp', 'N/A')}")
            st.write(f"**🏢 Сервис:** {violation.get('service', 'N/A')}")
            st.write(f"**⚠️ Тип нарушения:** {violation.get('error_type', 'N/A')}")
            st.write(f"**👤 Пользователь:** {violation.get('user_id', 'N/A')}")
            st.write(f"**🔑 Сессия:** {violation.get('session_id', 'N/A')}")
        
        with col2:
            st.subheader("🔗 Идентификаторы")
            st.write(f"**🆔 Trace ID:** `{violation.get('trace_id', 'N/A')}`")
            st.write(f"**📝 Request ID:** `{violation.get('request_id', 'N/A')}`")
            st.write(f"**🗂️ ID записи:** {violation.get('id', 'N/A')}")
        
        # Сообщение о нарушении
        st.subheader("📄 Сообщение о нарушении")
        if violation.get('error_message'):
            message = violation.get('error_message', '')
            if len(message) > 500:
                st.text_area("Сообщение о нарушении", message, height=150, disabled=True)
            else:
                st.code(message, language="text")
        else:
            st.info("Сообщение о нарушении отсутствует")
        
        # Контекст нарушения
        if violation.get('context'):
            st.subheader("📋 Контекст нарушения")
            context = violation.get('context', {})
            
            # Показываем ключевую информацию из контекста
            if 'user_message' in context:
                st.write(f"**💬 Сообщение пользователя:** {context['user_message']}")
            
            if 'category' in context:
                st.write(f"**🏷️ Категория:** {context['category']}")
            
            if 'confidence' in context:
                st.write(f"**🎯 Уровень уверенности:** {context['confidence']:.2f}")
            
            if 'processing_time' in context:
                st.write(f"**⏱️ Время обработки:** {context['processing_time']:.3f}с")
            
            if 'heuristic_check' in context:
                st.write(f"**🔍 Эвристическая проверка:** {'Да' if context['heuristic_check'] else 'Нет'}")
            
            if 'llm_available' in context:
                st.write(f"**🤖 LLM доступен:** {'Да' if context['llm_available'] else 'Нет'}")
            
            # Показываем полный контекст в expander
            with st.expander("📄 Полный контекст"):
                st.json(context)
        
        # Кнопки действий
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if violation.get('trace_id'):
                if st.button("🔍 Полный трейс", key=f"full_trace_violation_{violation.get('trace_id')}"):
                    with st.spinner("Загрузка полного трейса..."):
                        full_trace = get_full_trace(violation.get('trace_id'))
                        if full_trace:
                            show_full_trace_details(full_trace)
                        else:
                            st.error("Не удалось загрузить данные трейса")
        
        with col2:
            if violation.get('request_id'):
                if st.button("📋 Все нарушения по Request", key=f"request_violations_{violation.get('request_id')}"):
                    show_request_related_violations(violation.get('request_id'))
        
        with col3:
            if st.button("📊 Статистика по типу", key=f"violation_type_stats_{violation.get('error_type')}"):
                show_violation_type_statistics(violation.get('error_type'))


def show_request_related_violations(request_id):
    """Показать все нарушения безопасности связанные с конкретным request_id"""
    if not request_id:
        st.error("Request ID не указан")
        return
    
    try:
        response = requests.get(f"{MONITORING_SERVICE_URL}/security/violations?request_id={request_id}", timeout=5)
        if response.status_code == 200:
            related_violations = response.json()
            if related_violations:
                st.subheader(f"🔒 Все нарушения безопасности для Request ID: {request_id}")
                
                for i, violation in enumerate(related_violations):
                    with st.expander(f"Нарушение {i+1}: {violation.get('service')} - {violation.get('error_type')}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Время:** {violation.get('timestamp')}")
                            st.write(f"**Сервис:** {violation.get('service')}")
                        with col2:
                            st.write(f"**Тип:** {violation.get('error_type')}")
                            st.write(f"**Пользователь:** {violation.get('user_id')}")
                        
                        st.write(f"**Сообщение:** {violation.get('error_message')}")
                        
                        if violation.get('context'):
                            st.json(violation.get('context'))
            else:
                st.info(f"Для Request ID {request_id} не найдено других нарушений безопасности")
        else:
            st.error("Не удалось получить данные о нарушениях безопасности")
    except Exception as e:
        st.error(f"Ошибка при загрузке данных: {str(e)}")


def show_violation_type_statistics(error_type):
    """Показать статистику по типу нарушения безопасности"""
    if not error_type:
        st.error("Тип нарушения не указан")
        return
    
    try:
        response = requests.get(f"{MONITORING_SERVICE_URL}/security/violations?error_type={error_type}&hours=24", timeout=5)
        if response.status_code == 200:
            type_violations = response.json()
            if type_violations:
                st.subheader(f"📊 Статистика по типу нарушения: {error_type}")
                
                df_stats = pd.DataFrame(type_violations)
                
                # Статистика по сервисам
                if 'service' in df_stats.columns:
                    service_counts = df_stats['service'].value_counts()
                    st.write("**Распределение по сервисам:**")
                    for service, count in service_counts.items():
                        st.write(f"- {service}: {count} нарушений")

                # Статистика по времени
                if 'timestamp' in df_stats.columns:
                    df_stats['hour'] = pd.to_datetime(df_stats['timestamp']).dt.hour
                    hourly_counts = df_stats['hour'].value_counts().sort_index()
                    st.write("**Распределение по часам:**")
                    for hour, count in hourly_counts.items():
                        st.write(f"- {hour:02d}:00: {count} нарушений")
                
                # Общая статистика
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Всего нарушений", len(type_violations))
                with col2:
                    st.metric("Затронутых сервисов", df_stats['service'].nunique() if 'service' in df_stats.columns else 0)
                with col3:
                    st.metric("Затронутых пользователей", df_stats['user_id'].nunique() if 'user_id' in df_stats.columns else 0)
                
                # Анализ контекста
                if 'context' in df_stats.columns:
                    st.subheader("📋 Анализ контекста нарушений")
                    
                    # Анализ категорий
                    categories = []
                    confidences = []
                    for ctx in df_stats['context']:
                        if isinstance(ctx, dict):
                            if 'category' in ctx:
                                categories.append(ctx['category'])
                            if 'confidence' in ctx:
                                confidences.append(ctx['confidence'])
                    
                    if categories:
                        category_counts = pd.Series(categories).value_counts()
                        st.write("**Распределение по категориям:**")
                        for category, count in category_counts.items():
                            st.write(f"- {category}: {count} нарушений")
                    
                    if confidences:
                        st.write("**Статистика по уровню уверенности:**")
                        conf_series = pd.Series(confidences)
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Средний уровень", f"{conf_series.mean():.2f}")
                        with col2:
                            st.metric("Минимальный уровень", f"{conf_series.min():.2f}")
                        with col3:
                            st.metric("Максимальный уровень", f"{conf_series.max():.2f}")
                
            else:
                st.info(f"За последние 24 часа не найдено нарушений типа {error_type}")
        else:
            st.error("Не удалось получить данные статистики")
    except Exception as e:
        st.error(f"Ошибка при загрузке статистики: {str(e)}")


def show_detailed_error_analysis(error, error_category):
    """Показать подробный анализ выбранной ошибки"""
    with st.expander("🔍 Детальный анализ ошибки", expanded=True):

        # Основная информация об ошибке
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📋 Основная информация")
            st.write(f"**🕒 Время:** {error.get('timestamp', 'N/A')}")
            st.write(f"**🏢 Сервис:** {error.get('service', 'N/A')}")
            st.write(f"**⚠️ Тип ошибки:** {error.get('error_type', 'N/A')}")
            st.write(f"**🏷️ Категория:** {error_category}")
            st.write(f"**👤 Пользователь:** {error.get('user_id', 'N/A')}")
            st.write(f"**🔑 Сессия:** {error.get('session_id', 'N/A')}")

        with col2:
            st.subheader("🔗 Идентификаторы")
            st.write(f"**🆔 Trace ID:** `{error.get('trace_id', 'N/A')}`")
            st.write(f"**📝 Request ID:** `{error.get('request_id', 'N/A')}`")
            st.write(f"**🗂️ ID записи:** {error.get('id', 'N/A')}")

        # Полное сообщение об ошибке
        st.subheader("📄 Полное сообщение об ошибке")
        if error.get('error_message'):
            # Разбиваем длинное сообщение на части для лучшей читаемости
            message = error.get('error_message', '')
            if len(message) > 500:
                st.text_area("Сообщение об ошибке", message, height=150, disabled=True)
            else:
                st.code(message, language="text")
        else:
            st.info("Сообщение об ошибке отсутствует")

        # Кнопки действий
        col1, col2, col3 = st.columns(3)

        with col1:
            if error.get('trace_id'):
                if st.button("🔍 Полный трейс", key=f"full_trace_{error.get('trace_id')}_{error_category}"):
                    with st.spinner("Загрузка полного трейса..."):
                        full_trace = get_full_trace(error.get('trace_id'))
                        if full_trace:
                            show_full_trace_details(full_trace)
                        else:
                            st.error("Не удалось загрузить данные трейса")

        with col2:
            if error.get('request_id'):
                if st.button("📋 Все ошибки по Request", key=f"request_errors_{error.get('request_id')}_{error_category}"):
                    show_request_related_errors(error.get('request_id'))

        with col3:
            if st.button("📊 Статистика по типу", key=f"type_stats_{error.get('error_type')}_{error_category}"):
                show_error_type_statistics(error.get('error_type'))

        # Дополнительная информация (если есть)
        if error.get('stack_trace') or error.get('context'):
            st.subheader("🔧 Дополнительная информация")

            if error.get('stack_trace'):
                with st.expander("📄 Stack Trace"):
                    st.code(error.get('stack_trace', ''), language="text")

            if error.get('context'):
                with st.expander("📋 Контекст ошибки"):
                    st.json(error.get('context', {}))


def show_request_related_errors(request_id):
    """Показать все ошибки связанные с конкретным request_id"""
    if not request_id:
        st.error("Request ID не указан")
        return

    # Получаем все ошибки по request_id
    try:
        response = requests.get(f"{MONITORING_SERVICE_URL}/errors?request_id={request_id}", timeout=5)
        if response.status_code == 200:
            related_errors = response.json()
            if related_errors:
                st.subheader(f"🚨 Все ошибки для Request ID: {request_id}")

                for i, error in enumerate(related_errors):
                    with st.expander(f"Ошибка {i+1}: {error.get('service')} - {error.get('error_type')}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Время:** {error.get('timestamp')}")
                            st.write(f"**Сервис:** {error.get('service')}")
                        with col2:
                            st.write(f"**Тип:** {error.get('error_type')}")
                            st.write(f"**Категория:** {error.get('category')}")

                        st.write(f"**Сообщение:** {error.get('error_message')}")

                        if error.get('stack_trace'):
                            st.code(error.get('stack_trace'), language="text")
            else:
                st.info(f"Для Request ID {request_id} не найдено других ошибок")
        else:
            st.error("Не удалось получить данные об ошибках")
    except Exception as e:
        st.error(f"Ошибка при загрузке данных: {str(e)}")


def show_error_type_statistics(error_type):
    """Показать статистику по типу ошибки"""
    if not error_type:
        st.error("Тип ошибки не указан")
        return

    # Получаем статистику по типу ошибки за последние 24 часа
    try:
        response = requests.get(f"{MONITORING_SERVICE_URL}/errors?error_type={error_type}&start_date={datetime.now() - timedelta(hours=24)}", timeout=5)
        if response.status_code == 200:
            type_errors = response.json()
            if type_errors:
                st.subheader(f"📊 Статистика по типу ошибки: {error_type}")

                df_stats = pd.DataFrame(type_errors)

                # Статистика по сервисам
                if 'service' in df_stats.columns:
                    service_counts = df_stats['service'].value_counts()
                    st.write("**Распределение по сервисам:**")
                    for service, count in service_counts.items():
                        st.write(f"- {service}: {count} ошибок")

                # Статистика по времени
                if 'timestamp' in df_stats.columns:
                    df_stats['hour'] = pd.to_datetime(df_stats['timestamp']).dt.hour
                    hourly_counts = df_stats['hour'].value_counts().sort_index()
                    st.write("**Распределение по часам:**")
                    for hour, count in hourly_counts.items():
                        st.write(f"- {hour:02d}:00: {count} ошибок")

                # Общая статистика
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Всего ошибок", len(type_errors))
                with col2:
                    st.metric("Затронутых сервисов", df_stats['service'].nunique() if 'service' in df_stats.columns else 0)
                with col3:
                    st.metric("Затронутых пользователей", df_stats['user_id'].nunique() if 'user_id' in df_stats.columns else 0)

            else:
                st.info(f"За последние 24 часа не найдено ошибок типа {error_type}")
        else:
            st.error("Не удалось получить данные статистики")
    except Exception as e:
        st.error(f"Ошибка при загрузке статистики: {str(e)}")


def show_error_statistics(all_errors):
    """Показать общую статистику по ошибкам"""
    if not all_errors:
        st.info("Нет данных для статистики")
        return

    df_errors = pd.DataFrame(all_errors)
    if df_errors.empty:
        st.info("Нет данных для анализа")
        return

    # Основные метрики
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Всего ошибок", len(df_errors))

    with col2:
        st.metric("Типов ошибок", df_errors['error_type'].nunique() if 'error_type' in df_errors.columns else 0)

    with col3:
        st.metric("Затронутых сервисов", df_errors['service'].nunique() if 'service' in df_errors.columns else 0)

    with col4:
        st.metric("Затронутых пользователей", df_errors['user_id'].nunique() if 'user_id' in df_errors.columns else 0)

    # Распределение ошибок по типам
    if 'error_type' in df_errors.columns:
        st.subheader("📈 Распределение по типам ошибок")
        error_type_counts = df_errors['error_type'].value_counts()
        for error_type, count in error_type_counts.items():
            st.write(f"- {error_type}: {count} случаев")

    # Распределение ошибок по сервисам
    if 'service' in df_errors.columns:
        st.subheader("🏢 Распределение по сервисам")
        service_counts = df_errors['service'].value_counts()
        for service, count in service_counts.items():
            st.write(f"- {service}: {count} ошибок")

    # Распределение ошибок по времени
    if 'timestamp' in df_errors.columns:
        st.subheader("⏰ Распределение по времени")
        df_errors['hour'] = pd.to_datetime(df_errors['timestamp']).dt.hour
        hourly_counts = df_errors['hour'].value_counts().sort_index()
        for hour, count in hourly_counts.items():
            st.write(f"- {hour:02d}:00: {count} ошибок")

    # Топ проблемных сервисов
    if 'service' in df_errors.columns and 'error_type' in df_errors.columns:
        st.subheader("🔥 Топ проблемных комбинаций сервис-ошибка")
        service_error_counts = df_errors.groupby(['service', 'error_type']).size().reset_index(name='count')
        service_error_counts = service_error_counts.sort_values('count', ascending=False).head(10)

        st.dataframe(
            service_error_counts,
            column_config={
                "service": "Сервис",
                "error_type": "Тип ошибки",
                "count": st.column_config.NumberColumn("Количество", format="%d")
            },
            use_container_width=True
        )


# Кэширование данных для оптимизации
@st.cache_data(ttl=REFRESH_INTERVAL)
def get_stats() -> Dict[str, Any]:
    """Получить общую статистику системы"""
    try:
        response = requests.get(f"{MONITORING_SERVICE_URL}/stats", timeout=5)
        if response.status_code == 200:
            return response.json()
        return {}
    except Exception as e:
        st.error(f"Ошибка при получении статистики: {str(e)}")
        return {}

@st.cache_data(ttl=REFRESH_INTERVAL)
def get_traces_count(hours: int = 24) -> List[Dict[str, Any]]:
    """Получить количество трейсов по времени"""
    try:
        response = requests.get(f"{MONITORING_SERVICE_URL}/metrics/traces/count?hours={hours}", timeout=5)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        st.error(f"Ошибка при получении данных: {str(e)}")
        return []

@st.cache_data(ttl=REFRESH_INTERVAL)
def get_errors_count(hours: int = 24) -> List[Dict[str, Any]]:
    """Получить количество ошибок по времени"""
    try:
        response = requests.get(f"{MONITORING_SERVICE_URL}/metrics/errors/count?hours={hours}", timeout=5)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        st.error(f"Ошибка при получении данных: {str(e)}")
        return []


@st.cache_data(ttl=REFRESH_INTERVAL)
def get_errors_count_by_category(hours: int = 24) -> Dict[str, List[Dict[str, Any]]]:
    """Получить количество ошибок по категориям"""
    try:
        security_response = requests.get(f"{MONITORING_SERVICE_URL}/metrics/errors/count?hours={hours}&error_type=security", timeout=5)
        technical_response = requests.get(f"{MONITORING_SERVICE_URL}/metrics/errors/count?hours={hours}&error_type=technical", timeout=5)

        return {
            "security": security_response.json() if security_response.status_code == 200 else [],
            "technical": technical_response.json() if technical_response.status_code == 200 else []
        }
    except Exception as e:
        st.error(f"Ошибка при получении статистики по категориям: {str(e)}")
        return {"security": [], "technical": []}

@st.cache_data(ttl=REFRESH_INTERVAL)
def get_performance_data(hours: int = 24) -> List[Dict[str, Any]]:
    """Получить данные производительности"""
    try:
        response = requests.get(f"{MONITORING_SERVICE_URL}/metrics/performance?hours={hours}", timeout=5)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        st.error(f"Ошибка при получении данных: {str(e)}")
        return []

@st.cache_data(ttl=REFRESH_INTERVAL)
def get_services_summary(hours: int = 24) -> List[Dict[str, Any]]:
    """Получить сводку по сервисам"""
    try:
        response = requests.get(f"{MONITORING_SERVICE_URL}/metrics/services/summary?hours={hours}", timeout=5)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        st.error(f"Ошибка при получении данных: {str(e)}")
        return []

@st.cache_data(ttl=REFRESH_INTERVAL)
def get_recent_traces(limit: int = 10) -> List[Dict[str, Any]]:
    """Получить последние трейсы"""
    try:
        response = requests.get(f"{MONITORING_SERVICE_URL}/traces?limit={limit}", timeout=5)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        st.error(f"Ошибка при получении данных: {str(e)}")
        return []

@st.cache_data(ttl=REFRESH_INTERVAL)
def get_recent_errors(limit: int = 10) -> List[Dict[str, Any]]:
    """Получить последние ошибки"""
    try:
        response = requests.get(f"{MONITORING_SERVICE_URL}/errors?limit={limit}", timeout=5)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        st.error(f"Ошибка при получении данных: {str(e)}")
        return []


@st.cache_data(ttl=REFRESH_INTERVAL)
def get_security_violations(limit: int = 10) -> List[Dict[str, Any]]:
    """Получить нарушения безопасности"""
    try:
        response = requests.get(f"{MONITORING_SERVICE_URL}/security/violations?limit={limit}", timeout=5)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        st.error(f"Ошибка при получении данных: {str(e)}")
        return []

@st.cache_data(ttl=REFRESH_INTERVAL)
def get_security_violations_stats(hours: int = 24) -> Dict[str, Any]:
    """Получить статистику нарушений безопасности"""
    try:
        response = requests.get(f"{MONITORING_SERVICE_URL}/security/violations/stats?hours={hours}", timeout=5)
        if response.status_code == 200:
            return response.json()
        return {}
    except Exception as e:
        st.error(f"Ошибка при получении статистики: {str(e)}")
        return {}

@st.cache_data(ttl=REFRESH_INTERVAL)
def get_security_errors(limit: int = 10) -> List[Dict[str, Any]]:
    """Получить последние security ошибки (legacy)"""
    try:
        response = requests.get(f"{MONITORING_SERVICE_URL}/errors?category=security&limit={limit}", timeout=5)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        st.error(f"Ошибка при получении данных: {str(e)}")
        return []


@st.cache_data(ttl=REFRESH_INTERVAL)
def get_technical_errors(limit: int = 10) -> List[Dict[str, Any]]:
    """Получить последние технические ошибки"""
    try:
        response = requests.get(f"{MONITORING_SERVICE_URL}/errors/technical?limit={limit}", timeout=5)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        st.error(f"Ошибка при получении данных: {str(e)}")
        return []

@st.cache_data(ttl=REFRESH_INTERVAL)
def get_errors_stats(hours: int = 24) -> Dict[str, Any]:
    """Получить статистику ошибок"""
    try:
        response = requests.get(f"{MONITORING_SERVICE_URL}/errors/stats?hours={hours}", timeout=5)
        if response.status_code == 200:
            return response.json()
        return {}
    except Exception as e:
        st.error(f"Ошибка при получении статистики: {str(e)}")
        return {}


def get_full_trace(trace_id: str) -> Dict[str, Any]:
    """Получить полный трейс ошибки"""
    try:
        response = requests.get(f"{MONITORING_SERVICE_URL}/trace/{trace_id}/full", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            return data
        elif response.status_code == 404:
            st.error(f"Трейс с ID {trace_id} не найден")
            return {}
        else:
            st.error(f"Ошибка сервера при получении трейса: {response.status_code}")
            try:
                error_detail = response.json()
                st.error(f"Детали ошибки: {error_detail}")
            except Exception as e:
                st.error(f"Текст ответа: {response.text}")
            return {}
    except requests.exceptions.Timeout:
        st.error("Превышено время ожидания при получении трейса")
        return {}
    except requests.exceptions.ConnectionError:
        st.error("Не удалось подключиться к сервису мониторинга")
        return {}
    except Exception as e:
        st.error(f"Неожиданная ошибка при получении трейса: {str(e)}")
        return {}

@st.cache_data(ttl=30)  # Кэшируем на 30 секунд для health checks
def get_services_health() -> List[Dict[str, Any]]:
    """Получить статус health check всех сервисов"""
    services = [
        {"name": "API Gateway", "url": "http://api-gateway:8000/health", "port": 8000, "type": "http"},
        {"name": "Security Service", "url": "http://security-service:8001/health", "port": 8001, "type": "http"},
        {"name": "RAG Service", "url": "http://rag-service:8002/health", "port": 8002, "type": "http"},
        {"name": "Dialogue Service", "url": "http://dialogue-service:8003/health", "port": 8003, "type": "http"},
        {"name": "Monitoring Service", "url": "http://monitoring-service:8004/health", "port": 8004, "type": "http"},
        {"name": "Redis", "host": "redis", "port": 6379, "type": "tcp"},
        {"name": "PostgreSQL", "host": "db", "port": 5432, "type": "tcp"}
    ]

    health_statuses = []

    for service in services:
        try:
            if service["type"] == "tcp":
                # Для TCP сервисов (Redis, PostgreSQL) используем socket check
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                start_time = time.time()
                result = sock.connect_ex((service["host"], service["port"]))
                response_time = (time.time() - start_time) * 1000  # в миллисекундах
                sock.close()
                is_healthy = result == 0
            else:
                # Для HTTP сервисов делаем GET запрос
                start_time = time.time()
                response = requests.get(service["url"], timeout=3)
                response_time = (time.time() - start_time) * 1000  # в миллисекундах
                is_healthy = response.status_code == 200

            health_statuses.append({
                "service": service["name"],
                "status": "healthy" if is_healthy else "unhealthy",
                "response_time": f"{response_time:.1f}ms" if response_time else "N/A",
                "port": service["port"],
                "last_check": datetime.now().strftime("%H:%M:%S")
            })

        except Exception as e:
            health_statuses.append({
                "service": service["name"],
                "status": "unhealthy",
                "response_time": "Error",
                "port": service["port"],
                "last_check": datetime.now().strftime("%H:%M:%S")
            })

    return health_statuses

def main():
    """Основная функция дашборда"""

    # Sidebar с настройками
    st.sidebar.header("⚙️ Настройки")

    # Выбор периода времени
    time_periods = {
        "Последний час": 1,
        "Последние 6 часов": 6,
        "Последние 24 часа": 24,
        "Последние 7 дней": 168
    }

    selected_period = st.sidebar.selectbox(
        "Период времени:",
        list(time_periods.keys()),
        index=2
    )
    hours = time_periods[selected_period]

    # Автообновление
    auto_refresh = st.sidebar.checkbox("Автообновление", value=True)

    if auto_refresh:
        st.sidebar.info(f"Обновление каждые {REFRESH_INTERVAL} секунд")

    # Получение данных
    stats = get_stats()
    traces_data = get_traces_count(hours)
    errors_data = get_errors_count(hours)
    errors_by_category = get_errors_count_by_category(hours)
    performance_data = get_performance_data(hours)
    services_data = get_services_summary(hours)
    # recent_errors уже загружен глобально
    recent_traces = get_recent_traces()
    security_violations = get_security_violations()
    security_violations_stats = get_security_violations_stats(hours)
    security_errors = get_security_errors()
    technical_errors = get_technical_errors()
    errors_stats = get_errors_stats(hours)
    services_health = get_services_health()

    # Быстрый поиск и фильтры
    st.subheader("🔍 Быстрый анализ ошибок")

    if recent_errors:
        df_errors = pd.DataFrame(recent_errors)

        # Поиск по ключевым словам
        search_term = st.text_input("Поиск по сообщениям об ошибках:", placeholder="Введите ключевое слово...")

        # Применяем поиск
        if search_term:
            df_errors = df_errors[df_errors['error_message'].str.contains(search_term, case=False, na=False)]

        # Показываем найденные ошибки
        if not df_errors.empty:
            st.write(f"**Найдено ошибок:** {len(df_errors)}")

            # Показываем топ критичных ошибок
            if len(df_errors) > 5:
                st.subheader("🚨 Топ критичных ошибок")
                critical_errors = df_errors.head(5)
                for idx, error in critical_errors.iterrows():
                    with st.expander(f"🚨 {error.get('service')} - {error.get('error_type')} - {error.get('timestamp', '')[:19]}", expanded=False):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Сервис:** {error.get('service')}")
                            st.write(f"**Тип:** {error.get('error_type')}")
                            st.write(f"**Категория:** {error.get('category')}")
                        with col2:
                            st.write(f"**Пользователь:** {error.get('user_id', 'N/A')}")
                            st.write(f"**Время:** {error.get('timestamp', '')[:19]}")

                        # Краткое сообщение
                        message = error.get('error_message', '')
                        if len(message) > 200:
                            st.write(f"**Сообщение:** {message[:200]}...")
                        else:
                            st.write(f"**Сообщение:** {message}")

                        # Кнопки действий
                        if error.get('trace_id'):
                            if st.button("🔍 Полный трейс", key=f"quick_trace_{idx}"):
                                with st.spinner("Загрузка полного трейса..."):
                                    full_trace = get_full_trace(error.get('trace_id'))
                                    if full_trace:
                                        show_full_trace_details(full_trace)
                                    else:
                                        st.error("Не удалось загрузить данные трейса")
        else:
            st.info("Поиск не дал результатов")

        # Алерты о критичных ситуациях
        st.subheader("🚨 Критичные алерты")

        if recent_errors:
            df_errors = pd.DataFrame(recent_errors)

            alerts = []

            # Алерт: Много ошибок одного типа
            if 'error_type' in df_errors.columns:
                error_counts = df_errors['error_type'].value_counts()
                for error_type, count in error_counts.items():
                    if count >= 5:  # Порог для алерта
                        alerts.append(f"⚠️ **Высокая частота ошибки**: {error_type} ({count} раз)")

            # Алерт: Ошибки security
            if 'category' in df_errors.columns:
                security_errors_count = len(df_errors[df_errors['category'] == 'security'])
                if security_errors_count >= 3:
                    alerts.append(f"🔒 **Security алерт**: {security_errors_count} security ошибок")

            # Алерт: Затронуты многие пользователи
            if 'user_id' in df_errors.columns:
                affected_users = df_errors['user_id'].nunique()
                if affected_users >= 5:
                    alerts.append(f"👥 **Множественные пользователи**: {affected_users} пользователей затронуты")

            # Алерт: Ошибки в критических сервисах
            critical_services = ['api-gateway', 'security-service', 'monitoring-service']
            critical_errors = df_errors[df_errors['service'].isin(critical_services)] if 'service' in df_errors.columns else pd.DataFrame()
            if len(critical_errors) >= 3:
                alerts.append(f"🚨 **Критические сервисы**: {len(critical_errors)} ошибок в критических сервисах")

            # Показываем алерты
            if alerts:
                for alert in alerts:
                    st.error(alert)
            else:
                st.success("✅ Система работает стабильно - критичных алертов нет")

    st.divider()

    # Секция нарушений безопасности
    st.subheader("🔒 Нарушения безопасности")
    
    if security_violations_stats:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Всего нарушений", security_violations_stats.get('total_violations', 0))
        
        with col2:
            violations_by_type = security_violations_stats.get('violations_by_type', [])
            st.metric("Типов нарушений", len(violations_by_type))
        
        with col3:
            violations_by_service = security_violations_stats.get('violations_by_service', [])
            st.metric("Затронутых сервисов", len(violations_by_service))
        
        with col4:
            hourly_violations = security_violations_stats.get('hourly_violations', [])
            recent_violations = len([v for v in hourly_violations if v.get('count', 0) > 0])
            st.metric("Активных часов", recent_violations)
    
    # Детальная информация о нарушениях безопасности
    if security_violations:
        st.subheader("🚨 Последние нарушения безопасности")
        
        df_violations = pd.DataFrame(security_violations)
        if not df_violations.empty:
            # Показываем таблицу нарушений
            display_cols = ['timestamp', 'service', 'error_type', 'error_message', 'user_id', 'session_id']
            available_cols = [col for col in display_cols if col in df_violations.columns]
            
            if available_cols:
                st.dataframe(
                    df_violations[available_cols].head(10),
                    use_container_width=True,
                    column_config={
                        "timestamp": st.column_config.DatetimeColumn("Время", format="DD.MM.YYYY HH:mm:ss"),
                        "service": "Сервис",
                        "error_type": "Тип нарушения",
                        "error_message": st.column_config.TextColumn("Сообщение", width="large"),
                        "user_id": "Пользователь",
                        "session_id": "Сессия",
                    }
                )
            
            # Детальный анализ нарушений
            if len(df_violations) > 0:
                selected_violation_idx = st.selectbox(
                    "Выберите нарушение для детального анализа:",
                    range(len(df_violations.head(10))),
                    format_func=lambda x: f"{df_violations.iloc[x]['service']} - {df_violations.iloc[x]['error_type']} - {df_violations.iloc[x]['error_message'][:50]}...",
                    key="security_violation_select"
                )
                
                if selected_violation_idx is not None:
                    selected_violation = df_violations.iloc[selected_violation_idx]
                    show_detailed_security_violation(selected_violation)
    else:
        st.info("Нарушений безопасности не обнаружено")

    st.divider()

    # Панель Health Check всех сервисов
    st.subheader("🔍 Статус сервисов")

    if services_health:
        # Создаем колонки для каждого сервиса
        cols = st.columns(len(services_health))

        for i, service in enumerate(services_health):
            with cols[i]:
                # Определяем цвет и иконку в зависимости от статуса
                if service["status"] == "healthy":
                    color = "🟢"
                    bg_color = "#d4edda"  # светло-зеленый
                else:
                    color = "🔴"
                    bg_color = "#f8d7da"  # светло-красный

                # Создаем карточку сервиса
                st.markdown(f"""
                <div style="
                    background-color: {bg_color};
                    padding: 10px;
                    border-radius: 8px;
                    text-align: center;
                    margin: 2px;
                    border: 1px solid #ddd;
                ">
                    <div style="font-size: 1.2em; margin-bottom: 5px;">{color}</div>
                    <div style="font-size: 0.8em; font-weight: bold;">{service['service']}</div>
                    <div style="font-size: 0.7em; color: #666;">:{service['port']}</div>
                    <div style="font-size: 0.7em; color: #666;">{service['response_time']}</div>
                    <div style="font-size: 0.6em; color: #999;">{service['last_check']}</div>
                </div>
                """, unsafe_allow_html=True)

    st.divider()

    # Основные метрики
    if stats:
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.metric("Всего логов", f"{stats.get('total_logs', 0):,}")

        with col2:
            st.metric("Логов сегодня", f"{stats.get('logs_today', 0):,}")

        with col3:
            st.metric("Активных сервисов", stats.get('active_services', 0))

        with col4:
            error_rate = stats.get('error_rate_24h', 0)
            st.metric("Ошибка (%) за 24ч", f"{error_rate:.1f}")

        with col5:
            response_time = stats.get('avg_response_time', 0)
            st.metric("Среднее время ответа", f"{response_time:.2f}")

    # Дополнительные метрики ошибок
    if recent_errors:
        df_errors = pd.DataFrame(recent_errors)
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            security_count = len(df_errors[df_errors.get('category') == 'security']) if 'category' in df_errors.columns else 0
            st.metric("🔒 Security ошибок", security_count)

        with col2:
            technical_count = len(df_errors[df_errors.get('category') == 'technical']) if 'category' in df_errors.columns else 0
            st.metric("⚙️ Технических ошибок", technical_count)

        with col3:
            unique_services = df_errors['service'].nunique() if 'service' in df_errors.columns else 0
            st.metric("🏢 Затронутых сервисов", unique_services)

        with col4:
            unique_users = df_errors['user_id'].nunique() if 'user_id' in df_errors.columns else 0
            st.metric("👥 Затронутых пользователей", unique_users)

    st.divider()

    # Расширенная информация об ошибочных запросах
    if recent_errors:
        st.subheader("🚨 Детальный анализ ошибочных запросов")

        df_errors = pd.DataFrame(recent_errors)

        # Фильтры для анализа ошибок
        col1, col2, col3 = st.columns(3)

        # Инициализируем переменные по умолчанию
        selected_service = "Все"
        selected_error_type = "Все"
        selected_category = "Все"

        with col1:
            if 'service' in df_errors.columns:
                selected_service = st.selectbox(
                    "Фильтр по сервису:",
                    ["Все"] + sorted(df_errors['service'].unique().tolist())
                )

        with col2:
            if 'error_type' in df_errors.columns:
                selected_error_type = st.selectbox(
                    "Фильтр по типу ошибки:",
                    ["Все"] + sorted(df_errors['error_type'].unique().tolist())
                )

        with col3:
            if 'category' in df_errors.columns:
                selected_category = st.selectbox(
                    "Фильтр по категории:",
                    ["Все"] + sorted(df_errors['category'].unique().tolist())
                )

        # Применяем фильтры
        filtered_df = df_errors.copy()
        if selected_service != "Все":
            filtered_df = filtered_df[filtered_df['service'] == selected_service]
        if selected_error_type != "Все":
            filtered_df = filtered_df[filtered_df['error_type'] == selected_error_type]
        if selected_category != "Все":
            filtered_df = filtered_df[filtered_df['category'] == selected_category]

        # Показываем фильтрованные результаты
        if not filtered_df.empty:
            st.write(f"**Найдено ошибок:** {len(filtered_df)}")

            # Расширенная таблица с полной информацией
            st.dataframe(
                filtered_df[['timestamp', 'service', 'error_type', 'category', 'error_message', 'user_id', 'trace_id', 'request_id']].head(20),
                use_container_width=True,
                column_config={
                    "timestamp": st.column_config.DatetimeColumn("Время", format="DD.MM.YYYY HH:mm:ss"),
                    "service": "Сервис",
                    "error_type": "Тип ошибки",
                    "category": "Категория",
                    "error_message": st.column_config.TextColumn("Сообщение", width="large"),
                    "user_id": "Пользователь",
                    "trace_id": st.column_config.TextColumn("Trace ID", width="medium"),
                    "request_id": st.column_config.TextColumn("Request ID", width="medium"),
                }
            )

            # Экспорт данных
            csv_data = filtered_df.to_csv(index=False)
            st.download_button(
                label="📥 Экспортировать в CSV",
                data=csv_data,
                file_name="error_analysis.csv",
                mime="text/csv",
                key="download_errors"
            )
        else:
            st.info("По заданным фильтрам ошибок не найдено")

    st.divider()

    # Графики
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📈 Количество запросов по сервисам")

        if traces_data:
            df_traces = pd.DataFrame(traces_data)
            if not df_traces.empty:
                # Группировка по сервису и статусу
                if 'service' in df_traces.columns and 'status' in df_traces.columns:
                    st.write("**Запросы по сервисам:**")
                    service_status = df_traces.groupby(['service', 'status'])['count'].sum().reset_index()
                    for _, row in service_status.iterrows():
                        st.write(f"- {row['service']} ({row['status']}): {row['count']} запросов")
                else:
                    st.info("Недостаточно данных для отображения статистики запросов")
            else:
                st.info("Нет данных о запросах")
        else:
            st.info("Не удалось загрузить данные о запросах")

    with col2:
        st.subheader("🚨 Анализ ошибок и нарушений")

        # Создаем вкладки для разных типов ошибок
        tab1, tab2, tab3 = st.tabs(["🔒 Нарушения безопасности", "⚙️ Технические ошибки", "📊 Общая статистика"])

        with tab1:
            if security_violations_stats:
                st.write("**Статистика нарушений безопасности:**")
                
                # Статистика нарушений по типам
                violations_by_type = security_violations_stats.get('violations_by_type', [])
                if violations_by_type:
                    st.write("**Нарушения безопасности по типам:**")
                    for violation in violations_by_type:
                        st.write(f"- {violation.get('error_type', 'Неизвестно')}: {violation.get('count', 0)} случаев")

                # Статистика нарушений по сервисам
                violations_by_service = security_violations_stats.get('violations_by_service', [])
                if violations_by_service:
                    st.write("**Распределение нарушений по сервисам:**")
                    for violation in violations_by_service:
                        st.write(f"- {violation.get('service', 'Неизвестно')}: {violation.get('count', 0)} нарушений")

                # Статистика нарушений по времени
                hourly_violations = security_violations_stats.get('hourly_violations', [])
                if hourly_violations:
                    st.write("**Нарушения безопасности по часам:**")
                    for violation in hourly_violations:
                        hour = pd.to_datetime(violation.get('hour', '')).hour if violation.get('hour') else 'Н/Д'
                        count = violation.get('count', 0)
                        st.write(f"- {hour:02d}:00: {count} нарушений")
            else:
                st.info("Нет данных о нарушениях безопасности")

        with tab2:
            if errors_stats:
                st.write("**Статистика технических ошибок:**")
                
                # Статистика ошибок по типам
                errors_by_type = errors_stats.get('errors_by_type', [])
                if errors_by_type:
                    st.write("**Технические ошибки по типам:**")
                    for error in errors_by_type:
                        st.write(f"- {error.get('error_type', 'Неизвестно')}: {error.get('count', 0)} случаев")

                # Статистика ошибок по сервисам
                errors_by_service = errors_stats.get('errors_by_service', [])
                if errors_by_service:
                    st.write("**Распределение технических ошибок по сервисам:**")
                    for error in errors_by_service:
                        st.write(f"- {error.get('service', 'Неизвестно')}: {error.get('count', 0)} ошибок")
            else:
                st.info("Нет данных о технических ошибках")

        with tab3:
            if errors_stats:
                st.write("**Общая статистика ошибок:**")
                
                # Общие метрики
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Всего ошибок", errors_stats.get('total_errors', 0))
                
                with col2:
                    errors_by_category = errors_stats.get('errors_by_category', [])
                    security_count = sum(item['count'] for item in errors_by_category if item.get('category') == 'security')
                    st.metric("Security ошибок", security_count)
                
                with col3:
                    technical_count = sum(item['count'] for item in errors_by_category if item.get('category') == 'technical')
                    st.metric("Технических ошибок", technical_count)
                
                # Распределение по категориям
                if errors_by_category:
                    st.write("**Распределение ошибок по категориям:**")
                    for category in errors_by_category:
                        st.write(f"- {category.get('category', 'Неизвестно')}: {category.get('count', 0)} ошибок")
            else:
                st.info("Нет данных для общей статистики")

    # Производительность
    st.subheader("⚡ Производительность по сервисам")

    if performance_data:
        df_perf = pd.DataFrame(performance_data)
        if not df_perf.empty:
            col1, col2 = st.columns(2)

            with col1:
                if 'service' in df_perf.columns and 'avg_response_time' in df_perf.columns:
                    st.write("**Среднее время ответа по сервисам:**")
                    for _, row in df_perf.iterrows():
                        st.write(f"- {row['service']}: {row.get('avg_response_time', 0):.2f} мс")
                else:
                    st.info("Недостаточно данных о времени ответа")

            with col2:
                if 'service' in df_perf.columns and 'request_count' in df_perf.columns:
                    st.write("**Распределение запросов по сервисам:**")
                    for _, row in df_perf.iterrows():
                        st.write(f"- {row['service']}: {row.get('request_count', 0)} запросов")
                else:
                    st.info("Недостаточно данных о распределении запросов")
        else:
            st.info("Нет данных о производительности")
    else:
        st.info("Не удалось загрузить данные о производительности")

    # Расширенная сводка по сервисам с анализом ошибок
    st.subheader("📋 Анализ сервисов и ошибок")

    if services_data:
        df_services = pd.DataFrame(services_data)
        if not df_services.empty:
            # Добавляем информацию об ошибках в сводку по сервисам
            if recent_errors:
                df_errors = pd.DataFrame(recent_errors)

                # Создаем расширенную сводку
                services_summary = []
                for service in df_services['service'].unique():
                    service_data = df_services[df_services['service'] == service].iloc[0] if len(df_services[df_services['service'] == service]) > 0 else None
                    service_errors = df_errors[df_errors['service'] == service] if 'service' in df_errors.columns else pd.DataFrame()

                    summary = {
                        'service': service,
                        'total_requests': service_data['total_requests'] if service_data is not None else 0,
                        'successful_requests': service_data['successful_requests'] if service_data is not None else 0,
                        'failed_requests': service_data['failed_requests'] if service_data is not None else 0,
                        'avg_response_time': service_data['avg_response_time'] if service_data is not None else 0,
                        'error_rate': service_data['error_rate'] if service_data is not None else 0,
                        'total_errors': len(service_errors),
                        'security_errors': len(service_errors[service_errors.get('category') == 'security']) if 'category' in service_errors.columns else 0,
                        'technical_errors': len(service_errors[service_errors.get('category') == 'technical']) if 'category' in service_errors.columns else 0,
                        'unique_error_types': service_errors['error_type'].nunique() if 'error_type' in service_errors.columns else 0,
                        'affected_users': service_errors['user_id'].nunique() if 'user_id' in service_errors.columns else 0
                    }
                    services_summary.append(summary)

                df_extended_services = pd.DataFrame(services_summary)

                # Сортировка по количеству ошибок
                df_extended_services = df_extended_services.sort_values('total_errors', ascending=False)

                # Показываем расширенную таблицу
                st.dataframe(
                    df_extended_services,
                    use_container_width=True,
                    column_config={
                        "service": st.column_config.TextColumn("Сервис", width="medium"),
                        "total_requests": st.column_config.NumberColumn("Всего запросов", format="%d"),
                        "successful_requests": st.column_config.NumberColumn("Успешных", format="%d"),
                        "failed_requests": st.column_config.NumberColumn("Неудачных", format="%d"),
                        "avg_response_time": st.column_config.NumberColumn("Среднее время (мс)", format="%.2f"),
                        "error_rate": st.column_config.NumberColumn("Процент ошибок", format="%.2f%%"),
                        "total_errors": st.column_config.NumberColumn("Всего ошибок", format="%d"),
                        "security_errors": st.column_config.NumberColumn("🔒 Security", format="%d"),
                        "technical_errors": st.column_config.NumberColumn("⚙️ Технических", format="%d"),
                        "unique_error_types": st.column_config.NumberColumn("Типов ошибок", format="%d"),
                        "affected_users": st.column_config.NumberColumn("👥 Пользователей", format="%d"),
                    }
                )

                # Топ проблемных сервисов
                if len(df_extended_services) > 0:
                    st.subheader("🔥 Топ сервисов по количеству ошибок")
                    top_problematic = df_extended_services.head(10)

                    st.write("**Топ проблемных сервисов:**")
                    for _, row in top_problematic.iterrows():
                        st.write(f"- {row['service']}: {row['total_errors']} ошибок ({row['error_rate']:.1f}%)")

            else:
                # Показываем базовую сводку если нет данных об ошибках
                st.dataframe(
                    df_services,
                    use_container_width=True,
                    column_config={
                        "service": "Сервис",
                        "total_requests": "Всего запросов",
                        "successful_requests": "Успешных",
                        "failed_requests": "Неудачных",
                        "avg_response_time": st.column_config.NumberColumn(
                            "Среднее время (мс)",
                            format="%.2f"
                        ),
                        "error_rate": st.column_config.NumberColumn(
                            "Процент ошибок",
                            format="%.2f%%"
                        )
                    }
                )
        else:
            st.info("Нет данных о сервисах")
    else:
        st.info("Не удалось загрузить сводку по сервисам")

    # Недавние активности
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🔍 Последние трейсы")

        if recent_traces:
            df_traces = pd.DataFrame(recent_traces)
            if not df_traces.empty:
                # Показать последние 5 трейсов
                display_cols = ['timestamp', 'service', 'operation', 'status', 'duration']
                available_cols = [col for col in display_cols if col in df_traces.columns]

                if available_cols:
                    st.dataframe(
                        df_traces[available_cols].head(5),
                        use_container_width=True
                    )
                else:
                    st.info("Недостаточно данных о трейсах")
            else:
                st.info("Нет данных о трейсах")
        else:
            st.info("Не удалось загрузить трейсы")

    with col2:
        st.subheader("⚠️ Анализ ошибок")

        # Вкладки для разных типов ошибок
        error_tab1, error_tab2, error_tab3, error_tab4 = st.tabs(["🔒 Нарушения безопасности", "⚙️ Технические ошибки", "🔒 Security ошибки", "📊 Статистика"])

        with error_tab1:
            show_error_details(security_violations, "нарушения безопасности")

        with error_tab2:
            show_error_details(technical_errors, "technical")

        with error_tab3:
            show_error_details(security_errors, "security")

        with error_tab4:
            show_error_statistics(recent_errors)

    # Информация о системе
    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("ℹ️ О системе")
        st.write(f"**Время последнего обновления:** {datetime.now().strftime('%H:%M:%S')}")
        st.write(f"**URL сервиса мониторинга:** {MONITORING_SERVICE_URL}")
        st.write(f"**Период данных:** {selected_period}")

    with col2:
        st.subheader("🔗 Быстрые ссылки")
        st.markdown(f"[📊 API документация]({MONITORING_SERVICE_URL}/docs)")
        st.markdown(f"[🏥 Health Check]({MONITORING_SERVICE_URL}/health)")
        st.markdown("[📈 Swagger UI](http://localhost:8004/docs)")
        st.markdown("[🔄 Перезагрузить данные](#)")

    # Автообновление
    if auto_refresh:
        time.sleep(REFRESH_INTERVAL)
        st.rerun()

# Загружаем данные в начале для корректной работы
@st.cache_data(ttl=30)
def load_dashboard_data():
    """Загружаем все необходимые данные для dashboard"""
    try:
        recent_errors = get_recent_errors()
        stats = get_stats()
        services_data = get_services_summary()
        recent_traces = get_recent_traces()

        return recent_errors, stats, services_data, recent_traces
    except Exception as e:
        st.error(f"Ошибка загрузки данных: {str(e)}")
        return [], {}, [], []

# Загружаем данные в начале
recent_errors, stats, services_data, recent_traces = load_dashboard_data()

if __name__ == "__main__":
    main()
