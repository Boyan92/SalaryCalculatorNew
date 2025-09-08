import streamlit as st
import matplotlib.pyplot as plt
import sqlite3
import pandas as pd

# Данни за работните дни през 2025 г. в България
WORKING_DAYS_2025 = {
    "Януари": 22,
    "Февруари": 20,
    "Март": 20,
    "Април": 20,
    "Май": 19,
    "Юни": 21,
    "Юли": 23,
    "Август": 21,
    "Септември": 20,
    "Октомври": 23,
    "Ноември": 20,
    "Декември": 20
}

# --- База данни ---
def create_db():
    conn = sqlite3.connect('salaries.db')
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS salaries (
            egn TEXT,
            full_name TEXT,
            month TEXT,
            gross_salary_base REAL,
            supko_rate REAL,
            years_experience INTEGER,
            days_vacation INTEGER,
            days_sick INTEGER,
            days_absence INTEGER,
            days_unpaid INTEGER,
            PRIMARY KEY (egn, month)
        )
    ''')

    try:
        c.execute("ALTER TABLE salaries ADD COLUMN sick_leave_count INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


def add_data(egn, full_name, month, gross_salary_base, supko_rate, years_experience, days_vacation, days_sick,
             days_absence, days_unpaid, sick_leave_count):
    conn = sqlite3.connect('salaries.db')
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO salaries (egn, full_name, month, gross_salary_base, supko_rate, years_experience, days_vacation, days_sick, days_absence, days_unpaid, sick_leave_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        egn, full_name, month, gross_salary_base, supko_rate, years_experience, days_vacation, days_sick, days_absence,
        days_unpaid, sick_leave_count))
    conn.commit()
    conn.close()


def read_data():
    conn = sqlite3.connect('salaries.db')
    c = conn.cursor()
    c.execute('SELECT * FROM salaries')
    data = c.fetchall()
    conn.close()
    return data


def update_data(egn, month, new_gross_salary_base, new_supko_rate, new_years_experience, new_days_vacation,
                new_days_sick, new_days_absence, new_days_unpaid, new_sick_leave_count):
    conn = sqlite3.connect('salaries.db')
    c = conn.cursor()
    c.execute('''
        UPDATE salaries SET
        gross_salary_base = ?,
        supko_rate = ?,
        years_experience = ?,
        days_vacation = ?,
        days_sick = ?,
        days_absence = ?,
        days_unpaid = ?,
        sick_leave_count = ?
        WHERE egn = ? AND month = ?
    ''', (
        new_gross_salary_base, new_supko_rate, new_years_experience, new_days_vacation, new_days_sick, new_days_absence,
        new_days_unpaid, new_sick_leave_count, egn, month))
    conn.commit()
    conn.close()


def delete_data(egn, month):
    conn = sqlite3.connect('salaries.db')
    c = conn.cursor()
    c.execute('DELETE FROM salaries WHERE egn=? AND month=?', (egn, month))
    conn.commit()
    conn.close()


def get_previous_month_data(egn, current_month):
    months_order = list(WORKING_DAYS_2025.keys())
    current_index = months_order.index(current_month)

    conn = sqlite3.connect('salaries.db')
    c = conn.cursor()

    for i in range(current_index - 1, -1, -1):
        prev_month = months_order[i]
        c.execute(
            'SELECT gross_salary_base, supko_rate, years_experience, days_vacation, days_sick, days_absence, days_unpaid FROM salaries WHERE egn=? AND month=?',
            (egn, prev_month))
        result = c.fetchone()
        if result:
            gross_salary_base, supko_rate, years_experience, days_vacation, days_sick, days_absence, days_unpaid = result

            # Изчисляване на отработените дни за предходния месец
            total_working_days_prev = WORKING_DAYS_2025[prev_month]
            days_worked_prev = total_working_days_prev - days_vacation - days_sick - days_absence - days_unpaid

            # Проверка дали са отработени най-малко 10 дни
            if days_worked_prev >= 10:
                conn.close()
                return gross_salary_base, supko_rate, years_experience, total_working_days_prev
    conn.close()
    return None, None, None, None


def calculate_net_salary_with_absences(gross_salary, tzpb_rate, birth_year, month, days_vacation=0, days_sick=0,
                                       days_absence=0, days_unpaid=0, has_telk=False, years_experience=0,
                                       supko_rate=0.0, egn=None, sick_leave_count=1):
    # Осигурителни прагове за 2025
    min_insurance_income = 1077
    max_insurance_income = 4130

    # Доплащане за професионален опит
    supko_amount = gross_salary * (supko_rate / 100) * years_experience
    gross_salary_with_supko = gross_salary + supko_amount

    # Общ брой работни дни за избрания месец
    total_working_days = WORKING_DAYS_2025[month]

    # Изчисляване на отработени дни
    days_worked = total_working_days - days_vacation - days_sick - days_absence - days_unpaid

    # Данъчни ставки
    tax_rate = 0.10

    # Определяне на осигурителните ставки според годината на раждане
    if birth_year == "Преди 1960":
        pension_employee = 0.0878
        ozm_employee = 0.014
        unemployment_employee = 0.004
        dzpo_employee = 0.00
        health_employee = 0.032

        pension_employer = 0.1102
        ozm_employer = 0.021
        unemployment_employer = 0.006
        dzpo_employer = 0.00
        health_employer = 0.048
    else:
        pension_employee = 0.0658
        ozm_employee = 0.014
        unemployment_employee = 0.004
        dzpo_employee = 0.022
        health_employee = 0.032

        pension_employer = 0.0822
        ozm_employer = 0.021
        unemployment_employer = 0.006
        dzpo_employer = 0.028
        health_employer = 0.048

    tzpb_employer = tzpb_rate / 100

    # Проверка дали имаме достатъчно отработени дни в предходния месец
    prev_gross_salary_base, prev_supko_rate, prev_years_experience, prev_total_working_days = get_previous_month_data(
        egn, month)

    if prev_gross_salary_base is not None:
        prev_gross_with_supko = prev_gross_salary_base + (
                prev_gross_salary_base * (prev_supko_rate / 100) * prev_years_experience)
        daily_gross_salary_vacation = prev_gross_with_supko / prev_total_working_days
        st.info(
            f"Платеният отпуск е изчислен на базата на предходен месец с 10+ отработени дни. Среднодневна база: {daily_gross_salary_vacation:.2f} лв.")
    else:
        if days_worked >= 10:
            daily_gross_salary_vacation = gross_salary_with_supko / total_working_days
            st.info(
                f"Платеният отпуск е изчислен на базата на текущия месец. Среднодневна база: {daily_gross_salary_vacation:.2f} лв.")
        else:
            daily_gross_salary_vacation = 0
            st.warning(
                "Не са открити предходни месеци с достатъчно отработени дни, нито текущият месец отговаря на условията. Платеният отпуск няма да бъде изчислен.")

    # Изчисляване на заплатата по пера
    base_salary_part = (gross_salary_with_supko / total_working_days) * days_worked
    vacation_salary_part = daily_gross_salary_vacation * days_vacation
    sick_pay_part = 0
    unpaid_absence_part = 0

    gross_salary_worked = base_salary_part + vacation_salary_part

    # Болничните се изчисляват по различен начин (70%)
    # Първите 2 дни се плащат от работодателя за всеки отделен болничен, останалите от НОИ
    daily_sick_pay = (gross_salary_with_supko / total_working_days) * 0.7
    days_sick_employer = min(days_sick, 2 * sick_leave_count)
    days_sick_nssi = max(0, days_sick - days_sick_employer)

    sick_pay_employer = daily_sick_pay * days_sick_employer
    sick_pay_nssi = daily_sick_pay * days_sick_nssi

    # Осигурителен доход за здравни осигуровки върху болничните от НОИ (1077)
    sick_leave_insurance_base = (1077 / total_working_days) * days_sick_nssi
    health_insurance_sick_leave_employer = sick_leave_insurance_base * 0.048

    # Изчисляване на здравната осигуровка за неплатен отпуск
    health_insurance_unpaid_base = min_insurance_income / 2
    health_insurance_unpaid_total = (health_insurance_unpaid_base / total_working_days) * days_unpaid * 0.08

    # Общ брутен доход
    total_gross_income = gross_salary_worked + sick_pay_employer

    # Корекция на осигурителната основа
    insurance_base_income = gross_salary_worked + sick_pay_employer
    insurance_base = max(min(insurance_base_income, max_insurance_income), min_insurance_income)

    # Изчисляване на осигуровките за служител
    pension_employee_val = insurance_base * pension_employee
    ozm_employee_val = insurance_base * ozm_employee
    unemployment_employee_val = insurance_base * unemployment_employee
    dzpo_employee_val = insurance_base * dzpo_employee
    health_employee_val = insurance_base * health_employee

    # Общо осигуровки за служител
    total_doo_employee = pension_employee_val + ozm_employee_val + unemployment_employee_val
    total_insurance_employee = total_doo_employee + dzpo_employee_val + health_employee_val + health_insurance_unpaid_total

    # Изчисляване на осигуровките за работодател
    pension_employer_val = insurance_base * pension_employer
    ozm_employer_val = insurance_base * ozm_employer
    unemployment_employer_val = insurance_base * unemployment_employer
    dzpo_employer_val = insurance_base * dzpo_employer
    tzpb_val = insurance_base * tzpb_employer
    health_employer_val = insurance_base * health_employer

    # Общо осигуровки за работодател (включват и ЗО за болнични)
    total_doo_employer = pension_employer_val + ozm_employer_val + unemployment_employer_val
    total_insurance_employer = total_doo_employer + dzpo_employer_val + tzpb_val + health_employer_val + health_insurance_sick_leave_employer

    # Общо разходи за работодателя
    total_employer_cost = total_gross_income + total_insurance_employer + health_insurance_unpaid_total

    # Данъчна основа (брутна заплата, без болнични, минус осигуровките на служителя)
    taxable_income = (gross_salary_worked) - (
            total_insurance_employee - health_insurance_unpaid_total)

    # Прилагане на данъчно облекчение за ТЕЛК
    if has_telk:
        taxable_income = max(0, taxable_income - 660)

    # Данък върху дохода
    income_tax = taxable_income * tax_rate

    # Нетна заплата
    net_salary = total_gross_income - total_insurance_employee - income_tax

    return {
        'gross_salary_before_supko': gross_salary,
        'gross_salary_with_supko': gross_salary_with_supko,
        'supko_amount': supko_amount,
        'total_gross_income': total_gross_income,
        'net_salary': net_salary,
        'insurance_base': insurance_base,

        'pension_employee_rate': pension_employee,
        'ozm_employee_rate': ozm_employee,
        'unemployment_employee_rate': unemployment_employee,
        'dzpo_employee_rate': dzpo_employee,
        'health_employee_rate': health_employee,

        'pension_insurance_employee': pension_employee_val,
        'ozm_insurance_employee': ozm_employee_val,
        'unemployment_insurance_employee': unemployment_employee_val,
        'dzpo_insurance_employee': dzpo_employee_val,
        'health_insurance_employee': health_employee_val,
        'total_doo_employee': total_doo_employee,
        'total_insurance_employee': total_insurance_employee,
        'health_insurance_unpaid': round(health_insurance_unpaid_total, 2),

        'pension_employer_rate': pension_employer,
        'ozm_employer_rate': ozm_employer,
        'unemployment_employer_rate': unemployment_employer,
        'dzpo_employer_rate': dzpo_employer,
        'tzpb_employer_rate': tzpb_rate,
        'health_employer_rate': health_employer,

        'pension_insurance_employer': pension_employer_val,
        'ozm_insurance_employer': ozm_employer_val,
        'unemployment_insurance_employer': unemployment_employer_val,
        'dzpo_insurance_employer': dzpo_employer_val,
        'tzpb': tzpb_val,
        'health_insurance_employer': health_employer_val,
        'health_insurance_sick_leave_employer': health_insurance_sick_leave_employer,
        'total_doo_employer': total_doo_employer,
        'total_insurance_employer': total_insurance_employer,
        'total_employer_cost': total_employer_cost,

        'taxable_income': taxable_income,
        'income_tax': income_tax,

        'days_worked': days_worked,
        'total_working_days': total_working_days,
        'days_vacation': days_vacation,
        'days_sick': days_sick,
        'days_absence': days_absence,
        'days_unpaid': days_unpaid,
        'sick_pay_employer': sick_pay_employer,
        'sick_pay_nssi': sick_pay_nssi,
        'days_sick_employer': days_sick_employer,
        'days_sick_nssi': days_sick_nssi,

        'base_salary_part': base_salary_part,
        'vacation_salary_part': vacation_salary_part,
        'sick_pay_part': sick_pay_part,
        'unpaid_absence_part': unpaid_absence_part,
        'vacation_daily_base': daily_gross_salary_vacation
    }


# --- Интерфейс на Streamlit ---

# Инициализиране на базата данни
create_db()

st.set_page_config(
    page_title="Калкулатор за нетна заплата 2025",
    page_icon="💰",
    layout="wide"
)

st.title("💰 Калкулатор за нетна заплата 2025")
st.markdown("""
Изчислете **нетната си заплата** за 2025 година.
---
""")

# Разделение на функционалностите
tab1, tab2 = st.tabs(["Калкулатор на заплата", "Управление на данни"])

with tab1:
    st.header("Въведете вашите данни")
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Основни параметри")
        egn = st.text_input("ЕГН на служителя (задължително за изчисление на отпуск)", max_chars=10, key='egn_input')
        full_name = st.text_input("Име на служителя", key='name_input')
        gross_salary = st.number_input(
            "Брутна заплата (без доплащане за стаж, лв):",
            min_value=1050.0,
            max_value=10000.0,
            value=2267.0,
            step=50.0,
            help="Въведете основната брутна месечна заплата."
        )
        birth_year = st.selectbox(
            "Година на раждане:",
            options=["След 1960", "Преди 1960"],
            index=1,
            help="Изберете година на раждане."
        )
        has_telk = st.checkbox(
            "Има ТЕЛК",
            help="Отбележете, ако лицето притежава решение на ТЕЛК."
        )

    with col2:
        st.subheader("Трудов стаж, осигуровки и отсъствия")
        supko_rate = st.selectbox(
            "Доплащане за стаж (%):",
            options=[0.6, 0.7, 0.8, 0.9, 1.0],
            index=0,
            help="Изберете процент на доплащане за всяка година трудов стаж."
        )
        experience = st.number_input(
            "Години стаж:",
            min_value=0,
            max_value=50,
            value=0,
            step=1,
            help="Въведете години трудов стаж."
        )
        tzpb_rate = st.selectbox(
            "ТЗПБ (%):",
            options=[0.4, 0.5, 0.7, 0.9, 1.1],
            index=2,
            help="Изберете процента на ТЗПБ."
        )
        month = st.selectbox(
            "Месец на изчисление:",
            options=list(WORKING_DAYS_2025.keys()),
            index=8,
            help="Изберете месеца, за който правите изчислението."
        )
        st.info(f"Работните дни за **{month} 2025** са: **{WORKING_DAYS_2025[month]}**")
        days_vacation = st.number_input(
            "Дни в платен отпуск:",
            min_value=0,
            max_value=WORKING_DAYS_2025[month],
            value=0,
            step=1,
            help="Въведете броя на дните в платен годишен отпуск."
        )
        days_sick = st.number_input(
            "Дни в болничен (общо):",
            min_value=0,
            max_value=WORKING_DAYS_2025[month] - days_vacation,
            value=0,
            step=1,
            help="Въведете общия брой на дните в болничен."
        )
        sick_leave_count = st.number_input(
            "Брой болнични листа:",
            min_value=0,
            max_value=days_sick if days_sick > 0 else 1,
            value=0,
            step=1,
            help="Въведете броя на отделните болнични листа за месеца."
        )
        days_absence = st.number_input(
            "Дни самоотлъчка:",
            min_value=0,
            max_value=WORKING_DAYS_2025[month] - days_vacation - days_sick,
            value=0,
            step=1,
            help="Въведете броя на дните самоотлъчка. За тези дни не се дължат осигуровки."
        )
        days_unpaid = st.number_input(
            "Дни неплатен отпуск:",
            min_value=0,
            max_value=WORKING_DAYS_2025[month] - days_vacation - days_sick - days_absence,
            value=0,
            step=1,
            help="За тези дни се дължи здравна осигуровка, която се удържа от служителя."
        )

    st.markdown("---")
    col_buttons = st.columns(2)
    with col_buttons[0]:
        if st.button("Изчисли заплата", type="primary", use_container_width=True):
            if egn and full_name:
                result = calculate_net_salary_with_absences(
                    gross_salary,
                    tzpb_rate,
                    birth_year,
                    month,
                    days_vacation,
                    days_sick,
                    days_absence,
                    days_unpaid,
                    has_telk,
                    experience,
                    supko_rate,
                    egn,
                    sick_leave_count
                )

                st.success(f"### 💰 Нетна заплата: {result['net_salary']:,.2f} лв")
                st.info(f"Доплащане за стаж: **{result['supko_amount']:,.2f} лв**")

                # Показване на ключови показатели
                st.markdown("---")
                st.subheader("Ключови показатели")
                col_kpi_1, col_kpi_2, col_kpi_3, col_kpi_4 = st.columns(4)
                with col_kpi_1:
                    st.metric("Брутна заплата (основна)", f"{result['gross_salary_before_supko']:,.2f} лв")
                with col_kpi_2:
                    st.metric("Брутна заплата (общо)", f"{result['gross_salary_with_supko']:,.2f} лв")
                with col_kpi_3:
                    st.metric("Осигурителен доход", f"{result['insurance_base']:,.2f} лв")
                with col_kpi_4:
                    st.metric("Облагаем доход", f"{result['taxable_income']:,.2f} лв")

                # Разходи и удръжки
                st.markdown("---")
                st.subheader("Разходи и удръжки")
                col_deductions_1, col_deductions_2, col_deductions_3, col_deductions_4 = st.columns(4)
                with col_deductions_1:
                    st.metric("Общо осигуровки служител", f"{result['total_insurance_employee']:,.2f} лв",
                              delta=-result['total_insurance_employee'], delta_color="inverse")
                with col_deductions_2:
                    st.metric("Данък върху дохода", f"{result['income_tax']:,.2f} лв",
                              delta=-result['income_tax'], delta_color="inverse")
                with col_deductions_3:
                    st.metric("Разходи за работодател", f"{result['total_employer_cost']:,.2f} лв")
                with col_deductions_4:
                    st.metric("ЗО за неплатен отпуск", f"{result['health_insurance_unpaid']:,.2f} лв")

                # Визуализация на разпределението
                st.markdown("---")
                st.subheader("Графично представяне на разпределението")
                col_vis_1, col_vis_2 = st.columns([1, 1])
                with col_vis_1:
                    st.markdown("#### От гледна точка на служителя")
                    fig_employee, ax1 = plt.subplots(figsize=(8, 8))
                    labels_employee = ['Нетна заплата', 'Пенсионно осигуряване', 'ОЗМ',
                                       'Безработица', 'ДЗПО', 'Здравно осигуряване', 'ЗО за непл. отпуск', 'Данък']
                    values_employee = [
                        result['net_salary'],
                        result['pension_insurance_employee'],
                        result['ozm_insurance_employee'],
                        result['unemployment_insurance_employee'],
                        result['dzpo_insurance_employee'],
                        result['health_insurance_employee'],
                        result['health_insurance_unpaid'],
                        result['income_tax']
                    ]


                    def autopct_format(pct):
                        return f'{pct:.1f}%' if pct >= 3 else ''


                    ax1.pie(values_employee, labels=labels_employee, autopct=autopct_format, startangle=90,
                            textprops={'fontsize': 10})
                    ax1.set_title('Разпределение на дохода за служителя')
                    st.pyplot(fig_employee, use_container_width=True)

                with col_vis_2:
                    st.markdown("#### Разходи за работодателя")
                    fig_employer, ax2 = plt.subplots(figsize=(8, 8))
                    categories_employer = [
                        'Брутна заплата', 'Пенсионно (Р-л)', 'ОЗМ (Р-л)', 'Безработица (Р-л)',
                        'ДЗПО (Р-л)', 'ТЗПБ', 'Здравно (Р-л)', 'Здр. осиг. за болнични (Р-л)',
                        'ЗО за непл. отпуск (С-л)'
                    ]
                    values_employer = [
                        result['gross_salary_with_supko'], result['pension_insurance_employer'],
                        result['ozm_insurance_employer'],
                        result['unemployment_insurance_employer'], result['dzpo_insurance_employer'], result['tzpb'],
                        result['health_insurance_employer'], result['health_insurance_sick_leave_employer'],
                        result['health_insurance_unpaid']
                    ]
                    colors = ['#ff9999', '#66b3ff', '#ffcc99', '#99ff99', '#ff6b6b', '#4ecdc4', '#ff9ff3', '#c466ff',
                              '#e0e0e0']
                    bars = ax2.bar(categories_employer, values_employer, color=colors)
                    ax2.set_title('Разходи от гледна точка на работодателя')
                    ax2.set_ylabel('Сума (лв)')
                    plt.xticks(rotation=45, ha='right', fontsize=9)
                    for bar in bars:
                        height = bar.get_height()
                        ax2.annotate(f'{height:,.2f}', xy=(bar.get_x() + bar.get_width() / 2, height),
                                     xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=7,
                                     rotation=45)
                    plt.tight_layout()
                    st.pyplot(fig_employer, use_container_width=True)

                with st.expander("📊 Вижте подробно изчисление по пера"):
                    st.markdown("### Детайлен разчет на заплатата и осигуровките")
                    st.markdown("#### Разпределение на брутната заплата:")
                    st.markdown(f"""
                    | Перо | Стойност (лв) | Описание |
                    | :--- | :--- | :--- |
                    | **Основна заплата** | **{result['base_salary_part']:,.2f}** | За отработени дни |
                    | **Платен отпуск** | **{result['vacation_salary_part']:,.2f}** | За дни платен отпуск |
                    | **Болнични (от работодател)** | **{result['sick_pay_employer']:,.2f}** | За първите {result['days_sick_employer']} дни болничен |
                    | **Дни неплатен отпуск** | **{result['days_unpaid']}** | Без възнаграждение |
                    | **Дни самоотлъчка** | **{result['days_absence']}** | Без възнаграждение |
                    | **Общо брутен доход** | **{result['total_gross_income']:,.2f}** | Общата сума, от която се изчисляват удръжките |
                    """)
                    st.markdown("#### Основни суми и отработени дни:")
                    st.markdown(f"""
                    | Параметър | Стойност | Описание |
                    | :--- | :--- | :--- |
                    | **Брутна заплата (основна)** | **{result['gross_salary_before_supko']:,.2f} лв** | Въведената основна брутна заплата |
                    | Доплащане за стаж (СУПКО) | {result['supko_amount']:,.2f} лв | Доплащане за години трудов стаж |
                    | **Общо брутен доход** | **{result['gross_salary_with_supko']:,.2f} лв** | Обща брутна сума преди осигуровки и данъци |
                    | Общо работни дни за месеца | {result['total_working_days']} дни | Работни дни за избрания месец ({month}) |
                    | Отработени дни | {result['days_worked']} дни | Реално отработени дни |
                    | Дни в платен отпуск | {result['days_vacation']} дни | Дни, за които е ползван платен отпуск |
                    | Дни в болничен | {result['days_sick']} дни | Общ брой дни в болничен за месеца |
                    | Болнични, платени от работодателя | {result['days_sick_employer']} дни | Според броя на болничните листа |
                    | Болнични, платени от НОИ | {result['days_sick_nssi']} дни | Останалото от общия брой болнични дни |
                    | Възнаграждение от НОИ за болничен | {result['sick_pay_nssi']:,.2f} лв | За дните над 2, платени от НОИ |
                    | Дни самоотлъчка | {result['days_absence']} дни | Неплатени дни без осигуровки |
                    | **Дни неплатен отпуск** | **{result['days_unpaid']} дни** | **Дължима ЗО: {result['health_insurance_unpaid']:,.2f} лв.** |
                    """)
                    st.markdown("#### Осигуровки за служител:")
                    st.markdown(f"""
                    | Параметър | Стойност (лв) | Процент |
                    | :--- | :--- | :--- |
                    | Пенсионно осигуряване | {result['pension_insurance_employee']:,.2f} | {result['pension_employee_rate'] * 100:.2f}% |
                    | ОЗМ | {result['ozm_insurance_employee']:,.2f} | {result['ozm_employee_rate'] * 100:.2f}% |
                    | Безработица | {result['unemployment_insurance_employee']:,.2f} | {result['unemployment_employee_rate'] * 100:.2f}% |
                    | **Общо ДОО (служител)** | **{result['total_doo_employee']:,.2f}** | **{result['pension_employee_rate'] * 100 + result['ozm_employee_rate'] * 100 + result['unemployment_employee_rate'] * 100:.2f}%** |
                    | ДЗПО | {result['dzpo_insurance_employee']:,.2f} | {result['dzpo_employee_rate'] * 100:.2f}% |
                    | Здравно осигуряване | {result['health_insurance_employee']:,.2f} | {result['health_employee_rate'] * 100:.2f}% |
                    | **Здравна осигуровка за неплатен отпуск** | **{result['health_insurance_unpaid']:,.2f}** | |
                    | **Общо осигуровки служител** | **{result['total_insurance_employee']:,.2f}** | |
                    """)
                    st.markdown("#### Осигуровки за работодател:")
                    st.markdown(f"""
                    | Параметър | Стойност (лв) | Процент |
                    | :--- | :--- | :--- |
                    | Пенсионно осигуряване | {result['pension_insurance_employer']:,.2f} | {result['pension_employer_rate'] * 100:.2f}% |
                    | ОЗМ | {result['ozm_insurance_employer']:,.2f} | {result['ozm_employer_rate'] * 100:.2f}% |
                    | Безработица | {result['unemployment_insurance_employer']:,.2f} | {result['unemployment_employer_rate'] * 100:.2f}% |
                    | **Общо ДОО (работодател)** | **{result['total_doo_employer']:,.2f}** | **{result['pension_employer_rate'] * 100 + result['ozm_employer_rate'] * 100 + result['unemployment_employer_rate'] * 100:.2f}%** |
                    | ДЗПО | {result['dzpo_insurance_employer']:,.2f} | {result['dzpo_employer_rate'] * 100:.2f}% |
                    | ТЗПБ | {result['tzpb']:,.2f} | {tzpb_rate:.2f}% |
                    | Здравно осигуряване | {result['health_insurance_employer']:,.2f} | {result['health_employer_rate'] * 100:.2f}% |
                    | Здравни осигуровки за болнични | {result['health_insurance_sick_leave_employer']:,.2f} | |
                    | **Здравна осигуровка за неплатен отпуск** | **{result['health_insurance_unpaid']:,.2f}** | |
                    | **Общо осигуровки работодател** | **{result['total_insurance_employer']:,.2f}** | |
                    """)
                    st.markdown("#### Данъчно изчисление:")
                    st.markdown(f"""
                    | Параметър | Стойност (лв) | Описание |
                    | :--- | :--- | :--- |
                    | Осигурителена основа | {result['insurance_base']:,.2f} | База за изчисляване на осигуровките |
                    | Общо осигуровки служител | {result['total_insurance_employee']:,.2f} | |
                    | **Облагаем доход** | **{result['taxable_income']:,.2f}** | Заплата минус осигуровки и облекчение за ТЕЛК |
                    | Данък върху дохода (10%) | {result['income_tax']:,.2f} | |
                    | **Нетна заплата** | **{result['net_salary']:,.2f}** | |
                    """)
                    st.markdown(f"**Общо разходи за работодател:** **{result['total_employer_cost']:,.2f} лв**")
            else:
                st.error("Моля, въведете ЕГН и име на служителя, за да бъде възможно изчислението на отпуска.")

    with col_buttons[1]:
        if st.button("Запиши данни", use_container_width=True):
            if egn and full_name:
                add_data(egn, full_name, month, gross_salary, supko_rate, experience, days_vacation, days_sick,
                         days_absence, days_unpaid, sick_leave_count)
                st.success(f"Данните за служител {full_name} за месец {month} бяха успешно записани.")
            else:
                st.error("Моля, попълнете ЕГН и име на служителя.")

with tab2:
    st.header("Управление на данни за заплати")

    data = read_data()
    df = pd.DataFrame(data,
                      columns=['ЕГН', 'Име', 'Месец', 'Брутна Заплата', 'СУПКО %', 'Години стаж', 'Дни отпуск',
                               'Дни болничен', 'Дни самоотлъчка', 'Дни неплатен', 'Брой болнични листа'])

    st.subheader("Всички записи")
    st.dataframe(df, use_container_width=True)

    st.markdown("---")
    st.subheader("Редактиране и изтриване на записи")

    col_crud = st.columns(2)
    with col_crud[0]:
        egn_edit = st.text_input("Въведете ЕГН на запис за редактиране/изтриване:", key='egn_edit')
        month_edit = st.selectbox("Изберете месец на запис за редактиране/изтриване:",
                                  options=list(WORKING_DAYS_2025.keys()), key='month_edit')

    if egn_edit and month_edit:
        row_to_edit = df[(df['ЕГН'] == egn_edit) & (df['Месец'] == month_edit)]
        if not row_to_edit.empty:
            st.info(f"Редактирате запис за {row_to_edit['Име'].iloc[0]} за месец {month_edit}")

            with st.form(key='edit_form'):
                new_gross_salary_base = st.number_input("Нова брутна заплата:",
                                                        value=row_to_edit['Брутна Заплата'].iloc[0])
                new_supko_rate = st.selectbox("Нов СУПКО %:", options=[0.6, 0.7, 0.8, 0.9, 1.0],
                                              index=[0.6, 0.7, 0.8, 0.9, 1.0].index(row_to_edit['СУПКО %'].iloc[0]))
                new_years_experience = st.number_input("Нови години стаж:", value=row_to_edit['Години стаж'].iloc[0])
                new_days_vacation = st.number_input("Нови дни отпуск:", value=row_to_edit['Дни отпуск'].iloc[0])
                new_days_sick = st.number_input("Нови дни болничен:", value=row_to_edit['Дни болничен'].iloc[0])
                new_sick_leave_count = st.number_input("Нов брой болнични листа:",
                                                       value=row_to_edit['Брой болнични листа'].iloc[0], min_value=1)
                new_days_absence = st.number_input("Нови дни самоотлъчка:",
                                                   value=row_to_edit['Дни самоотлъчка'].iloc[0])
                new_days_unpaid = st.number_input("Нови дни неплатен отпуск:",
                                                  value=row_to_edit['Дни неплатен'].iloc[0])

                col_edit_delete = st.columns(2)
                with col_edit_delete[0]:
                    if st.form_submit_button("Запази промени"):
                        update_data(egn_edit, month_edit, new_gross_salary_base, new_supko_rate, new_years_experience,
                                    new_days_vacation, new_days_sick, new_days_absence, new_days_unpaid,
                                    new_sick_leave_count)
                        st.success("Записът беше успешно актуализиран!")
                        st.experimental_rerun()
                with col_edit_delete[1]:
                    if st.form_submit_button("Изтрий запис"):
                        delete_data(egn_edit, month_edit)
                        st.success("Записът беше успешно изтрит!")
                        st.experimental_rerun()
        else:
            st.warning("Не е намерен запис с този ЕГН и месец.")

# Допълнителна информация
st.markdown("---")
st.sidebar.markdown("---")
st.sidebar.info("Калкулатор за заплата. \n\n" "Разработен от Боян Беличев, Старши експерт, отдел РППФД, ДБТ - Пловдив.")