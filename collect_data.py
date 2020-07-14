from pykrx import stock
from selenium import webdriver
import bs4
import datetime
import pandas as pd
import pandas_datareader as pdr
import time
import numpy as np
import re

class collect_data:
    # 날짜 형식 맞추기 위해 - 없애기
    def bar_remover(date):
        return date.split('-')[0]+date.split('-')[1]+date.split('-')[2]

    # 18년 1월 1일부터 가져올 수 있게 구축한 코드
    def get_stock_by_day(code, start_date):
        start_date_no_bar = collect_data.bar_remover(start_date)
        start_date = start_date

        # end_date는 오늘 날짜로 고정
        today = datetime.datetime.today().strftime('%Y%m%d')  # krx는 YYYYMMDD 형식, 야후는 YYYY-MM-DD 형식
        stock_df = stock.get_market_ohlcv_by_date(start_date_no_bar, today, code, adjusted=True)  # 시가 고가 저가 종가 거래량
        stock_df2 = stock.get_market_fundamental_by_date(start_date_no_bar, today, code)  # DIV BPS PER EPS PBR
        today_pdr = datetime.datetime.today().strftime('%Y-%m-%d')
        gold = pdr.get_data_yahoo('GC=F', start=start_date, end=today_pdr)[['Adj Close', 'Volume']]  # 금값
        gold.columns = ['Adj Close_gold', 'Volume_gold']
        nikkei = pdr.DataReader('^N225', 'yahoo', start=start_date, end=today_pdr)[['Adj Close', 'Volume']]  # 일본 지수
        nikkei.columns = ['Adj Close_nikkei', 'Volume_nikkei']
        crude_oil = pdr.get_data_yahoo('CL=F', start=start_date, end=today_pdr)[['Adj Close', 'Volume']]  # 유가
        crude_oil.columns = ['Adj Close_oil', 'Volume_oil']
        change = pd.Series(pdr.get_data_yahoo('KRW=X', start=start_date, end=today_pdr)['Adj Close'])  # 환율
        # 데이터 leftjoin
        data = pd.concat([stock_df, stock_df2], axis=1)
        data = pd.merge(data, gold, how='left', left_index=True, right_index=True)
        data = pd.merge(data, nikkei, how='left', left_index=True, right_index=True)
        data = pd.merge(data, crude_oil, how='left', left_index=True, right_index=True)
        data = pd.merge(data, change, how='left', left_index=True, right_index=True)
        data.columns = ['시가', '고가', '저가', '종가', '거래량', 'DIV', 'BPS', 'PER', 'EPS', 'PBR', 'Adj Close_gold', 'Volume_gold',
                        'Adj Close_nikkei', 'Volume_nikkei', 'Adj Close_oil', 'Volume_oil', 'Adj Close_change']
        # 기존에 사용했던 가장 최근의 값으로 채우는 방법 이거 쓰면 거의 다날라감
        data = data.fillna(method="pad")
        # 주가 자체의 값이 아니라 등락율을 구하기로 해서 다음날과 비교해서 올라가면 1 아니면 0 마지막날은 그대로
        for i in range(len(data['종가'])):
            if i == 0:
                continue
            elif i > 0 and i < (len(data['종가']) - 1):
                if data['종가'][i] < data['종가'][(i + 1)]:
                    data['종가'][i] = 1
                else:
                    data['종가'][i] = 0
            else:
                pass
        return data


    def nlp_news(text):
        try:
            idx = re.search("▶", text).start()
            text = text[:idx]
        except:
            pass
        re_pattern = r'(웰크론)+'
        text = re.sub(re_pattern, '', text)
        re_pattern = r'[일/이/삼/사/오/육/칠/팔/구/십/백][만\천]\s?[원]'
        text = re.sub(re_pattern, 'money', text)
        re_pattern = r'\d+[원]'
        text = re.sub(re_pattern, 'money', text)
        re_pattern = r'\d+[시]|[0-9]+[분]'
        text = re.sub(re_pattern, '', text)
        re_pattern = r'[0-9]+[일]'
        text = re.sub(re_pattern, '', text)
        re_pattern = r'\w*\s*기자'
        text = re.sub(re_pattern, '', text)
        re_pattern = r'\d{4}.\d{2}.\d{2}'
        text = re.sub(re_pattern, '', text)
        re_pattern = r'[a-zA-Z0-9+-_.]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
        text = re.sub(re_pattern, '', text)
        re_pattern = r'[[]-=+,#/\?:^$.@*\"※~&%ㆍ!』\\‘|\(\)\[\]\<\>`\'…]'
        text = re.sub(re_pattern, '', text)
        re_pattern = r'\[[^)]*\]'
        text = re.sub(re_pattern, '', text)
        re_pattern = r'\n'
        new_text = re.sub(re_pattern, '', text)
        return new_text

    def news_finder(stock_id, start_date):

        start_date = start_date
        stock_name = stock.get_market_ticker_name(stock_id)

        # 네이버 금융 뉴스 섹션에 접속
        driver = webdriver.Chrome(executable_path="./chromedriver.exe")
        url = "https://finance.naver.com/news/"
        driver.get(url)

        driver.find_element_by_xpath('//*[@id="newsMainTop"]/div/div[2]/form/div/input').click()  # 검색창 초기화
        driver.find_element_by_xpath('//*[@id="newsMainTop"]/div/div[2]/form/div/input').send_keys(
            stock_name)  # 주식 이름 검색창에 입력
        driver.find_element_by_xpath('//*[@id="newsMainTop"]/div/div[2]/form/div/a').click()  # 검색 아이콘 클릭해서 실행

        now = datetime.datetime.now()
        today_date = str(now.strftime('%Y-%m-%d'))

        result_url = driver.current_url
        new_url = result_url + "&sm=title.basic&pd=4&stDateStart=" + start_date + "&stDateEnd=" + today_date  # 제목에서만 설정 & Start 날짜 직접 설정 가능!
        driver.get(new_url)

        # 몇 페이지까지 존재하는지 알아보자.
        bs_obj = bs4.BeautifulSoup(driver.page_source, "html.parser")  # 뷰티풀숩 object 생성
        last = bs_obj.find("td", {"class": "pgRR"})
        a = last.find('a', href=True)
        last_page_num = int(a['href'].split('page=')[1])

        # last_page_num 개의 페이지 URL을 pages라는 리스트에 담아보자.
        page_numbering = list(range(1, last_page_num + 1))
        pages = []
        for i in range(1, last_page_num):
            pages.append(new_url + "&page=" + str(i))

        # 빈 데이터프레임 생성
        df = pd.DataFrame(columns=("date", "title", "content"))

        # 빈 데이터프레임에 크롤링한 기사 본문 내용들을 채워넣기
        for page in pages:
            driver.get(page)
            bs_obj = bs4.BeautifulSoup(driver.page_source, "html.parser")

            # 깔끔한 작업을 위해 필요한 영역만 남기고 나머지는 무시하자
            news_list = bs_obj.find("dl", {"class": "newsList"})
            news_titles_1 = news_list.find_all("dt", {"class": "articleSubject"})
            news_titles_2 = news_list.find_all("dd", {
                "class": "articleSubject"})  # 네이버 뉴스는 썸네일이 있는 뉴스와 없는 뉴스의 태그가 다르게 설정되어 있네요.
            news_titles = news_titles_1 + news_titles_2  # 그래서 작업을 2번 한 후에 합치는 방식을 썼습니다.
            del news_titles_1, news_titles_2  # 필요없는 변수 제거

            for title in news_titles:
                temp = title.find('a', href=True)
                news_url = "https://finance.naver.com" + temp['href']
                driver.get(news_url)  # 개별 뉴스들을 클릭하는 동작을 실행시킨다.
                bs_obj = bs4.BeautifulSoup(driver.page_source, "html.parser")

                if len(driver.window_handles) > 1:  # 팝업창이 있는 경우
                    time.sleep(1)
                    driver.switch_to_window(driver.window_handles[1])
                    driver.close()  # 팝업창 종료
                    driver.switch_to_window(driver.window_handles[0])  # 원래창으로 복귀

                else:  # 팝업창이 없는 경우

                    # 기사 제목 크롤링
                    title = driver.find_element_by_xpath('//*[@id="contentarea_left"]/div[2]/div[1]/div[2]/h3').text

                    # 기사 업로드 날짜 크롤링
                    date = driver.find_element_by_xpath(
                        '//*[@id="contentarea_left"]/div[2]/div[1]/div[2]/div/span').text

                    # 기사 본문 크롤링
                    content = collect_data.nlp_news(driver.find_element_by_xpath('//*[@id="content"]').text)

                    df.loc[len(df)] = [date, title, content]  # 빈 데이터프레임에 행 추가

        # id와 name이라는 column을 만들고 해당 값으로 동일하게 채워넣는다.
        df['id'] = stock_id
        df['name'] = stock_name
        driver.close()

        return df

    def time_remover(date):
        return date.split(" ")[0]

    def preprocessing_news(stock_id, start_date):
        start_date = start_date
        temp = collect_data.news_finder(stock_id, start_date)
        temp['date'] = temp[['date']].applymap(collect_data.time_remover)
        date_values = temp['date'].unique()

        # 빈 데이터프레임 생성
        df = pd.DataFrame(columns=("날짜", "title", "content"))

        for day in date_values:
            grouped = temp.groupby('date')
            temp_day = grouped.get_group(day)
            title_list = [temp_day['title'].tolist()]
            content_list = [temp_day['content'].tolist()]
            df.loc[len(df)] = [day, title_list, content_list]  # 빈 데이터프레임에 행 추가

        ndf = df.set_index(['날짜'])
        return ndf

    def news_price_merge(stock_id, start_date):
        start_date = start_date
        left = collect_data.preprocessing_news(stock_id, start_date)
        right = collect_data.get_stock_by_day(stock_id, start_date)
        merged = left.join(right, how='inner')  # 여기서는 index 값이 날짜이기 때문에 동일한 인덱스(날짜) 기준으로 데이터프레임을 병합한다.

        return merged
