import requests
import json
import pickle
import time
from tqdm import tqdm
from urllib  import parse
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from .naver_item_scrapper import *
from utils import NaverOptionGet
from agent import *
import os
from agent import *
import config

################쿠팡 HTML 불러오기################
def CoupangLinkGet(url_kword, n_top=10,):
    headers = {'User-Agent' : 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36', "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3"}
    url_query = 'https://www.coupang.com/np/search?component=&q='
    url_tail1 = '&channel=user'
    url = url_query+url_kword+url_tail1
    result = requests.get(url, headers=headers)
    result.raise_for_status() # 웹페이지 정상 확인
    html = result.text

    #html parsing
    soup = BeautifulSoup(html, 'html.parser')
    root = 'https://www.coupang.com'
    coupang_ntop_url = []
    qurey_arr = soup.select('ul#productList li.search-product a:has(span.number)')
    for i in range(n_top):
        coupang_ntop_url.append(root+qurey_arr[i]['href'])
    return coupang_ntop_url

################네이버 JSON으로 상품정보 불러오기################
def NaverLinkGet(keyword, driver, n_top=10,):
    
    url= 'https://search.shopping.naver.com'
    chrome_options = Options() ## 옵션 추가를 위한 준비
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222") ## 디버깅 옵션 추가

    # 크롬 드라이버 생성
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    driver.implicitly_wait(3) ## 연결 후 3초간 기다리

    try:
        pop_e = driver.find_element(By.CSS_SELECTOR, "div._buttonArea_button_area_2o-U6 > button._buttonArea_button_1jZae")
        pop_e.click()
    except:
        pass

    search_e = driver.find_element(By.CSS_SELECTOR, "input._searchInput_search_text_3CUDs")

    search_e.send_keys(keyword)

    search_btn_e = driver.find_element(By.CSS_SELECTOR, "button._searchInput_button_search_1n1aw")
    search_btn_e.click()
    driver.implicitly_wait(1)

    filter_e = driver.find_elements(By.CSS_SELECTOR, "a.subFilter_sort__lhuHl")
    filter_e[4].click()
    driver.implicitly_wait(1)
    
    naverpay_e = driver.find_element(By.CSS_SELECTOR, "ul.subFilter_seller_filter__snFam > li:nth-child(3) > a.subFilter_filter___O_rt")
    naverpay_e.click()

    scroll_down_to_end(driver)

    link_e = driver.find_elements(By.CSS_SELECTOR, 'a[rel=noopener].product_link__TrAac.linkAnchor')

    naver_ntop_url = []
    for i in range(n_top):
        naver_ntop_url.append(link_e[i].get_attribute('href'))
    
    return naver_ntop_url

################네이버 direct link에서 정보 불러오기################
def NaverFinalUrl(keyword, n_top):
    chrome_options = Options() ## 옵션 추가를 위한 준비
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222") ## 디버깅 옵션 추가
    # chrome_options.add_argument("headless")
    driver = webdriver.Chrome(options=chrome_options)
    n_top =n_top
    count = 0
    naver_url_lst = []
    
    url_list = NaverLinkGet(keyword, driver, 30)

    data_details = []
    data_reviews = []
    images_urls = [] 
    
    with tqdm(total=n_top, ascii=True) as pbar:
        for url in url_list:
            if count==n_top:
                break
            driver.get(url)
            driver.implicitly_wait(3)    
            if driver.find_elements(By.CSS_SELECTOR, "a._3C8i4VFUIv._3SXdE7K-MC.N\=a\:GNB\.shopping._nlog_click"):
                scrapped_data_path = os.path.join("database", "Naver_item_"+str(count+1)+".bin")
                review_data_path = os.path.join("database", "Naver_item_review_"+str(count+1)+".bin")
                result_detail, result_review, result_image_url = Naver_selenium_scraper(driver, scrapped_data_path, review_data_path)
                result_detail['product_number'] = count+1 #product number 라는 key 값 추가
                
                #옵션 가져오기
                opt_btn_lst =driver.find_elements(By.CSS_SELECTOR, '[data-shp-area-id*=opt]._nlog_impression_element')
                option_info = {'options':dict()}
                for i in range(len(opt_btn_lst)//2):
                    NaverOptionGet(driver, i, [], option_info['options'])
                    driver.refresh()
                result_detail.update(option_info)

                #vision_gpt 
                vision_info = vision_gpt(result_image_url)
                result_detail['product detail form images'] = vision_info
                #review rating 
                if config.review_compare_mode : #한 개씩 리뷰의 점수를 평가한 후 평균낸 점수
                    review_score = review_rating_one(result_review['리뷰']) # 리뷰들의 평균 점수 return
                else : #한 번에 10개의 리뷰를 모두 고려한 점수
                    review_score = review_rating_all(result_review['리뷰']) # 리뷰들의 평균 점수 return
                
                
                #compare_information : compare agent에게 제공할 정보 : 이름, 가격, 할인율, 번호, 리뷰 평균 점수...
                compare_information = {"product_number":count+1, "Product_name" : result_detail["상품명"], "discount_rate" : result_detail["할인율"], "price" : result_detail["현재 가격"], "review_positivity_score" : review_score, 'number of reviews' : result_review['리뷰 수'], "Star rating" : result_review['총 평점'] }

                data_details.append(result_detail)
                data_reviews.append(compare_information)
                images_urls.append(result_image_url)
                naver_url_lst.append(url)
                count+=1
                pbar.update(1)
            
    driver.quit()
    return naver_url_lst, data_details, data_reviews


################컬리 HTML 불러오기################
#컬리는 CSR 방식이라 Selenium을 통해 접근 한 후 HTML 불러와야함
def KurlyLinkGet(url_kword, n_top=10):
    url_query = "https://www.kurly.com/search?sword="
    url_tail1 = '&page=1&per_page=96&sorted_type=4'
    url = url_query+url_kword+url_tail1

    # 옵션 생성
    options = webdriver.ChromeOptions()
    # 창 숨기는 옵션 추가
    # options.add_argument("headless")
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222") ## 디버깅 옵션 추가

    driver = webdriver.Chrome(options=options)
    driver.get(url)
    driver.implicitly_wait(5)

    html = driver.page_source

    # driver 종료
    driver.quit()

    #html parsing
    soup = BeautifulSoup(html, 'html.parser')
    root = 'https://www.kurly.com'
    kurly_ntop_url = []

    qurey_arr = soup.select('div.css-11kh0cw a')
    len_link = min(len(qurey_arr),n_top)
    if len_link < n_top:
        print(f"컬리에서 해당 검색어로 검색되는 최대 상품 수가 {len_link}개 입니다")
    
    for i in range(len_link):
        kurly_ntop_url.append(root+qurey_arr[i]['href'])
    return kurly_ntop_url

################컬리 direct link에서 정보 불러오기################
def KurlyFinalUrl(keyword, n_top):
    kurly_url_list = KurlyLinkGet(keyword, n_top)

    # 웹드라이버 옵션 생성
    options = webdriver.ChromeOptions()
    # 창 숨기는 옵션 추가
    # options.add_argument("headless")
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    driver = webdriver.Chrome(options=options)
    
    # 해당 link별로 정보 가져오기
    for url in tqdm(kurly_url_list, ascii=True):
        driver.get(url)
        
        



################Gmarket HTML 불러오기################
def GmarketLinkGet(url_kword, n_top=10):
    headers = {'User-Agent' : 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36', "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3"}
    url_query = 'https://browse.gmarket.co.kr/search?keyword='
    url_tail1 = '&s=8'
    url = url_query+url_kword+url_tail1

    result = requests.get(url, headers=headers)
    result.raise_for_status() # 웹페이지 정상 확인
    html = result.text

    #html parsing
    soup = BeautifulSoup(html, 'html.parser')
    gmarket_ntop_url = []
    qurey_arr = soup.select('div.box__item-title span a.link__item')
    for i in range(n_top):
        gmarket_ntop_url.append(qurey_arr[i]['href'])
    return gmarket_ntop_url


if __name__ == '__main__':
    
    #Parameter Set
    keyword = input("Search KeyWord 입력:")
    n_top = int(input("검색 상위 N값 입력:"))

    #keyword parsing
    url_kword = parse.quote(keyword)
    
    #Get Links
    # func_arr = [CoupangLinkGet, NaverFinalUrl, KurlyLinkGet, GmarketLinkGet]
    # fina_link_lst = []
    # for f in tqdm(func_arr):
    #     if f==NaverFinalUrl:
    #         fina_link_lst+=f(keyword, n_top)
    #     else:
    #         fina_link_lst+=f(url_kword, n_top)
    #Create txt file   
    
    #Get Links-> 네이버만
    fina_link_lst = NaverFinalUrl(keyword,n_top)
    
    with open("./finalLink.pickle", "wb") as fw:
        pickle.dump(fina_link_lst, fw)
    print("완료!!")