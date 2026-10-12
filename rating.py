from urllib.request import Request, urlopen
from bs4 import BeautifulSoup
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re


@st.cache_data
def get_years():
    req = Request(url='https://rating.unecon.ru/index.php?up=none',
                  headers=headers)
    with urlopen(req, timeout=30) as response:
        print("STATUS:", response.status)
        response = response.read().decode("utf-8")

    soup = BeautifulSoup(response)
    courses_html = soup.select("div.filter > ul > li")[0].findAll("a")
    years_list = [int(re.search(r"y=(\d+)", course['href']).group(1)) for course in courses_html]
    return years_list


@st.cache_data
def get_profiles(year):
    req = Request(url=f'https://rating.unecon.ru/index.php?y={year}&up=none',
                  headers=headers)
    with urlopen(req, timeout=30) as response:
        print("STATUS:", response.status)
        response = response.read().decode("utf-8")

    soup = BeautifulSoup(response)
    profiles_html = soup.select("div.filter > ul > li")[3].findAll("a")
    profiles_dict = dict()
    for option in profiles_html:
        profiles_dict[option.text] = option['href']
    return profiles_dict


@st.cache_data
def get_semesters(href):
    req = Request(url='https://rating.unecon.ru/' + href,
                  headers=headers)
    with urlopen(req, timeout=30) as response:
        print("STATUS:", response.status)
        response = response.read().decode("utf-8")

    soup = BeautifulSoup(response)
    semesters_dict = dict()
    semesters_html = soup.select("div.filter > ul > li")[4].findAll("a")
    for option in semesters_html:
        semesters_dict[option.text] = option['href']
    semesters_dict['Не выбран'] = None
    return semesters_dict


@st.cache_data
def get_data(href):
    req = Request(url='https://rating.unecon.ru/' + href,
                  headers=headers)
    with urlopen(req, timeout=30) as response:
        print("STATUS:", response.status)
        response = response.read().decode("utf-8")

    soup = BeautifulSoup(response)
    subjects_info = [tag.text for tag in soup.find('ul', class_='upp_descr').findAll('li')]
    subjects = pd.DataFrame(
        [re.match(r'\d+\.\s*(\S+)\s*-\s*(.*?)\s*\((.*?)\)', s).groups()
         for s in subjects_info],
        columns=['abbr', 'name', 'type'])
    students_html = soup.select("table tbody tr")
    data = []
    for stud in students_html:
        tag_a = stud.find('a')
        if tag_a is not None:
            stud_id = int(re.search(r"stud=(\d+)", tag_a['href']).group(1))
            check_group = stud.findAll('td')[2].text
            group = check_group if '-' in check_group else None
            tag = stud.find('a')
            grades = [float(tag.text) if tag.text != '' else None for tag in stud.findAll("td", class_="w50 no_mobile")]
            data.append([stud_id, group, tag.text, tag['href']] + grades)
        # else student's data is hidden and not available
    df = pd.DataFrame(data, columns=['id', 'group', 'name', 'href'] + subjects['abbr'].to_list()).set_index('id')
    return df, subjects


def show_subjects_boxplot(df, subjects, include_exam, include_zachet, student):
    mask = (
            (include_exam & subjects["type"].isin(exam_types)) |
            (include_zachet & ~subjects["type"].isin(exam_types))
    )

    selected_subjects = subjects.loc[mask, "abbr"].tolist()

    fig = px.box(
        df[selected_subjects].dropna(axis=1, how="all"),
        title="Распределение оценок по предметам",
        labels={
            "variable": "Предмет",
            "value": "Баллы"
        }
    )
    fig.add_hline(y=60, line_dash="dash", line_width=1, layer="below")
    fig.add_hline(y=70, line_dash="dash", line_width=1, layer="below")
    fig.add_hline(y=85, line_dash="dash", line_width=1, layer="below")

    fig.update_yaxes(range=[0, 100])

    if student is not None:
        stud_info = df.loc[student]
        grades = stud_info[selected_subjects].dropna()

        fig.add_trace(
            go.Scatter(
                x=grades.index,
                y=grades.values,
                mode="markers",
                name=stud_info['name'] + str_format_group(stud_info['group']),
                marker=dict(
                    size=8,
                    color="lime",
                    line=dict(
                        color="darkgreen",
                        width=1
                    )
                )
            )
        )
        fig.update_layout(
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.5,
                xanchor="left",
                x=0
            )
        )
    st.plotly_chart(fig, width='stretch')
    with st.popover("Предметы"):
        for _, row in subjects[
            subjects["abbr"].isin(selected_subjects)
        ].iterrows():
            st.write(f"**{row['abbr']}** — {row['name']} ({row['type']})")


def show_mean_boxplot(df, subjects, i):
    exam_subjects = st.session_state.get(f'exam_subjects{i}')
    zachet_subjects = st.session_state.get(f'zachet_subjects{i}')
    fig = go.Figure()

    fig.add_trace(
        go.Box(
            y=df[exam_subjects].mean(axis=1),
            name="Оцениваемые дисциплины"
        )
    )
    fig.add_trace(
        go.Box(
            y=df[zachet_subjects].mean(axis=1),
            name="Зачетные дисциплины"
        )
    )
    fig.update_layout(
        title="Средние баллы студентов",
        xaxis_title="Тип контроля",
        yaxis_title="Средний балл"
    )

    fig.update_yaxes(range=[0, 100])
    fig.add_hline(y=60, line_dash="dash", line_width=1, layer="below")
    fig.add_hline(y=70, line_dash="dash", line_width=1, layer="below")
    fig.add_hline(y=85, line_dash="dash", line_width=1, layer="below")

    fig.update_yaxes(range=[0, 100])
    fig.update_layout(
        legend=dict(
            orientation="h",
            yanchor="bottom",
            xanchor="left",
            y=-0.7,
            x=0
        )
    )
    fill_colors = ["deeppink", "greenyellow"]
    border_colors = ["hotpink", "yellow"]
    for j in range(1, n_cols + 1):
        df_j = st.session_state.get(f'df{j}')
        student_j = st.session_state.get(f'student{j}')
        if student_j is not None:
            stud_info = df_j.loc[student_j]
            fig.add_trace(
                go.Scatter(
                    x=["Оцениваемые дисциплины",
                       "Зачетные дисциплины"],
                    y=[df_j.loc[student_j, st.session_state.get(f'exam_subjects{j}')].mean(),
                       df_j.loc[student_j, st.session_state.get(f'zachet_subjects{j}')].mean()],
                    mode="markers",
                    name=stud_info['name'] + str_format_group(stud_info['group']),
                    marker=dict(
                        size=10,
                        color=fill_colors[j - 1],
                        symbol="star",
                        line=dict(
                            color=border_colors[j - 1],
                            width=1
                        )
                    )
                )
            )
    st.plotly_chart(fig, width='stretch', key=f'mean{i}')


def str_format_group(group):
    return f' ({group})' if group is not None else ''


def show_all_semesters(semesters, student):
    exams = []
    zachets = []
    student_exams = []
    student_zachets = []
    sem_numbers = [int(re.findall(r"\d+", semester)[0]) for semester in semesters.keys()]
    for semester in semesters.keys():
        df, subjects = get_data(semesters[semester])
        exam_subjects = subjects.loc[subjects["type"].isin(exam_types), "abbr"]
        zachet_subjects = subjects.loc[~subjects["type"].isin(exam_types), "abbr"]
        exams.append(df[exam_subjects].mean(axis=None))
        zachets.append(df[zachet_subjects].mean(axis=None))
        if student is not None:
            stud_info = df.loc[student]
            student_exams.append(stud_info[exam_subjects].mean())
            student_zachets.append(stud_info[zachet_subjects].mean())

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Оцениваемые дисциплины", "Зачетные дисциплины")
    )

    # Экзамены
    fig.add_trace(
        go.Bar(name="Средний балл по направлению", x=sem_numbers, y=exams),
        row=1, col=1
    )
    if student is not None:
        fig.add_trace(
            go.Bar(
                name=stud_info['name'],
                x=sem_numbers,
                y=student_exams),
            row=1, col=1
        )

    # Зачёты
    fig.add_trace(
        go.Bar(name="Средний балл по направлению", x=sem_numbers, y=zachets),
        row=1, col=2
    )
    if student is not None:
        fig.add_trace(
            go.Bar(
                name=stud_info['name'],
                x=sem_numbers,
                y=student_zachets),
            row=1, col=2
        )

    fig.update_layout(
        barmode="group",
        height=500,
        title="Динамика среднего балла по семестрам",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            xanchor="left",
            y=-0.3,
            x=0
        )
    )

    fig.update_yaxes(
        range=[0, 100],
        title_text="Средний балл"
    )
    st.plotly_chart(fig, width='stretch', key=f'hist{i}')


def show_column(col, i):
    with col:
        year = st.selectbox(
            label=f"{i} - Год поступления",
            options=reversed(years),
            key=f'year{i}'
        )

        profiles = get_profiles(year)

        profile = st.selectbox(
            label=f"{i} - Направление",
            options=list(profiles.keys()),
            key=f'profile{i}'
        )

        if profile != 'Не выбрано':
            semesters = get_semesters(profiles[profile])

            semester = st.selectbox(
                label=f"{i} - Семестр",
                options=list(reversed(semesters.keys())),
                key=f'semester{i}'
            )

            if semester != 'Не выбран':
                df, subjects = get_data(semesters[semester])

                st.session_state[f"df{i}"] = df
                st.session_state[f"subjects{i}"] = subjects

                student = st.selectbox(
                    label=f"{i} - Студент",
                    options=[None] + df.index.to_list(),
                    format_func=lambda stud_id: df.loc[stud_id, "name"] + str_format_group(df.loc[stud_id, 'group'])
                    if stud_id is not None else "Не выбран",
                    key=f'student{i}'
                )

                exam_subjects = subjects.loc[subjects["type"].isin(exam_types), "abbr"]
                zachet_subjects = subjects.loc[~subjects["type"].isin(exam_types), "abbr"]
                st.session_state[f"exam_subjects{i}"] = exam_subjects
                st.session_state[f"zachet_subjects{i}"] = zachet_subjects

                selected_subject_types = st.pills(
                    label=f"{i} - Тип предмета",
                    options=["Экзамен/дифф. зачет", "Зачет"],
                    selection_mode="multi",
                    default=["Экзамен/дифф. зачет", "Зачет"],
                    key=f'selected_subject_types{i}'
                )
                include_exam = "Экзамен/дифф. зачет" in selected_subject_types
                include_zachet = "Зачет" in selected_subject_types
                show_subjects_boxplot(df, subjects, include_exam, include_zachet, student)
                if semester != 'Не выбран':
                    show_mean_boxplot(st.session_state.get(f'df{i}'), st.session_state.get(f'subjects{i}'), i=i)
                show_all_semesters({k: v for k, v in semesters.items() if k != 'Не выбран'}, student)


headers = {
    "domain-id": "www",
    "accept": "application/json, text/plain, */*",
    "origin": "https://rating.unecon.ru",
    "referer": "https://rating.unecon.ru/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/154.0.0.0 Safari/537.36"
    ),
}

st.set_page_config(
    page_title="Сравнение успеваемости по направлениям",
    layout="wide"
)

n_cols = 2

years = get_years()
exam_types = ["Экзамен", "дифф.зач."]

cols = st.columns(n_cols)

for i in range(1, n_cols + 1):
    show_column(cols[i - 1], i)
