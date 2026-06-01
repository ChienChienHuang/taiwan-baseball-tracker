from flask import Flask, render_template, jsonify
import requests

app = Flask(__name__)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time
import json
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

def fetch_lin_stats():
    url = "https://npb.jp/bis/players/33935152.html"
    try:
        # 使用 request 抓取
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 定位表格最新年度那一行 (tr)
        row = soup.select("section:nth-of-type(3) table tbody tr")[-1]
        tds = row.find_all("td")
        return {
            "avg": tds[20].text,        # 打率
            "hr": tds[9].text,          # 全壘打
            "rbi": tds[11].text,         # 打點
            "h_ab": f"{tds[6].text}/{tds[4].text}" # 安打/打數
        }
    except:
        return {"avg": "--", "hr": "--", "rbi": "--", "h_ab": "--/--"}

def fetch_npb_stats(player_id, player_type='pitcher'):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    url = f"https://pacificleague.com/zh-CHT/player/{player_id}"
    
    # 初始化預設值
    if player_type == 'pitcher':
        results = {"ERA": "--", "K/9": "--", "BB/9": "--"}
        metrics = ['ERA', 'K/9', 'BB/9']
    else:
        results = {"OPS": "--", "ISO": "--", "BB/K": "--"}
        metrics = ['OPS', 'ISO', 'BB/K']
    
    try:
        driver.get(url)
        time.sleep(3)
        # 使用更精準的 XPath 抓取數據對應
        for metric in metrics:
            try:
                # 假設結構為 span 標籤內包含標題，下一個元素為數據
                xpath = f"//*[contains(text(), '{metric}')]/following::span[1]"
                val = driver.find_element(By.XPATH, xpath).text.strip()
                results[metric] = val
            except:
                pass
        return results
    finally:
        driver.quit()

def fetch_kbo_stats(player_id):
    url = f"https://www.koreabaseball.com/Record/Player/PitcherDetail/Basic.aspx?playerId={player_id}"
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        driver.get(url)
        time.sleep(5)
        
        tables = driver.find_elements(By.TAG_NAME, "table")
        
        # 重新確認欄位 (根據 Log)
        # 第 0 個表格的 cells
        t0 = tables[0].find_elements(By.TAG_NAME, 'td')
        
        # 強制印出前幾個欄位確認對應關係，方便除錯
        print(f"DEBUG - W: {t0[4].text}, L: {t0[5].text}")
        
        # 這裡直接強制指定正確的索引
        wins = t0[5].text.strip()
        losses = t0[6].text.strip()
        
        # 第 1 個表格包含 SO (奪三振)
        t1 = tables[1].find_elements(By.TAG_NAME, 'td')
        so_value = t1[4].text.strip() 
        
        return {
            "era": t0[1].text.strip(),
            "w_l": f"{wins}勝-{losses}敗",
            "ip": t0[12].text.strip(),
            "so": so_value
        }
    except Exception as e:
        print(f"解析資料失敗: {e}")
        return None
    finally:
        driver.quit()

def fetch_milb_stats(player_url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    try:
        driver.get(player_url)
        time.sleep(8)
        
        # 直接抓取第一個表格 (索引 0)
        tables = driver.find_elements(By.TAG_NAME, "table")
        target_table = tables[0]
        rows = target_table.find_elements(By.TAG_NAME, "tr")
        
        # 根據您的 DEBUG 資訊：
        # 表格 0 的第二行 (row[1]) 就是 2026 數據
        # 投手表格結構: G(0), W-L(1), ERA(2), IP(3), SO(4), WHIP(5)
        # 注意：這是依據表格內容的 "td" 數量，請依實際抓到的 cell 索引調整
        cells = rows[1].find_elements(By.TAG_NAME, "td")
        
        # 抓取表格
        tables = driver.find_elements(By.TAG_NAME, "table")
        target_table = tables[0]
        rows = target_table.find_elements(By.TAG_NAME, "tr")

        # 假設 2026 出現在第 1 行 (row[1])
        data_row = rows[1] 
        cells = data_row.find_elements(By.TAG_NAME, "td")
        header_text = rows[0].text
        
        if "ERA" in header_text:
            # 投手：
            stats = {
                "type": "pitcher",
                "era": cells[2].text,
                "so": cells[4].text,
                "ip": cells[3].text,
                "w_l": cells[1].text
            }
        # 野手邏輯 (修正版)
        if "AVG" in header_text:
            cells = rows[1].find_elements(By.TAG_NAME, "td")
            stats = {
                "type": "fielder",
                "avg": cells[1].text,     # 索引 1 是 AVG
                "hr": cells[2].text,      # 索引 2 是 HR
                "rbi": cells[3].text,     # 索引 3 是 RBI
                "h_ab": f"--安/{cells[0].text}打數" # 索引 0 是 AB (表格沒顯示安打數 H，所以設為 --)
            }
        return stats
    except Exception as e:
        print(f"DEBUG: 抓取失敗 {e}")
        return {"era": "--", "so": "--", "ip": "--", "w_l": "--"}
    finally:
        driver.quit()
@app.route('/')
def home():
    return render_template('index.html')

def fetch_mlb_stats(player_id, is_milb=False):
    try:
        # 若為小聯盟，改從 milb 連結抓取
        if is_milb:
            return {"type": "minor", "is_major": False}
        
        url = f"https://statsapi.mlb.com/api/v1/people/{player_id}?hydrate=stats(group=[pitching,hitting],type=[season])"
        response = requests.get(url, timeout=4)
        if response.status_code != 200: return None
        
        data = response.json()
        if not data.get('people'): return None
        
        player_info = data['people'][0]
        stats_list = player_info.get('stats', [])
        
        result = {
            "position": player_info.get('primaryPosition', {}).get('name', '位置未知'),
            "bat_throw": f"長打/投球：{player_info.get('batSide', {}).get('code', '-')}{player_info.get('pitchHand', {}).get('code', '-')}",
            "type": "unknown",
            "is_major": True
        }
        
        if stats_list:
            season_stats = stats_list[0]['splits'][0]['stat']
            if 'era' in season_stats: 
                result.update({
                    "type": "pitcher", "era": season_stats.get('era', '-'),
                    "so": season_stats.get('strikeOuts', 0), "ip": season_stats.get('inningsPitched', '0.0'),
                    "w_l": f"{season_stats.get('wins', 0)}勝-{season_stats.get('losses', 0)}敗"
                })
            else: 
                result.update({
                    "type": "bg_batter", "avg": season_stats.get('avg', '-'),
                    "hr": season_stats.get('homeRuns', 0), "rbi": season_stats.get('rbi', 0),
                    "h_ab": f"{season_stats.get('hits', 0)}安/{season_stats.get('atBats', 0)}打數"
                })
        return result
    except Exception as e:
        return None
npb_ids = {
        "宋家豪": "516123",
        "古林睿煬": "525124",
        "徐若熙": "526126",
        "孫易磊": "524139",
        "蕭齊": "525126",
        "林冠臣": "525117",
        "陽柏翔": "525112",
        "陳睦衡": "525127",
        "張峻瑋": "525128",
}

# 全球旅外台將大數據 API (2026 精準官方分流版)
@app.route('/api/player/<name>')
def get_player_data(name):
    # 1. 2026 現役旅美資料庫
    mlb_database = {
        "鄧愷威": {"id": "678906", "official_link": "https://www.mlb.com/player/kai-wei-teng-678906", "team": "休士頓太空人 (MLB)", "pos": "pitcher"},
        "李灝宇": {"id": "701678", "official_link": "https://www.mlb.com/player/hao-yu-lee-701678", "team": "底特律老虎 (MLB)", "pos": "fielder"},
        "鄭宗哲": {"id": "691907", "official_link": "https://www.milb.com/player/tsung-che-cheng-691907", "team": "波士頓紅襪體系 (MiLB 3A)", "pos": "fielder","bat_throw": "左投右打"},
        "陳柏毓": {"id": "696040", "official_link": "https://www.milb.com/player/po-yu-chen-696040", "team": "匹茲堡海盜體系 (MiLB 3A)", "pos": "pitcher","bat_throw": "左投右打"},
        "林昱珉": {"id": "801179", "official_link": "https://www.milb.com/player/yu-min-lin-801179", "team": "亞利桑那響尾蛇體系 (MiLB 3A)", "pos": "pitcher","bat_throw": "左投左打"},
        "莊陳仲敖": {"id": "800018", "official_link": "https://www.milb.com/player/chen-zhong-ao-zhuang-800018", "team": "奧克蘭運動家體系 (MiLB 3A)", "pos": "pitcher","bat_throw": "右投右打"},
        "劉致榮": {"id": "692617", "official_link": "https://www.milb.com/player/chih-jung-liu-692617", "team": "波士頓紅襪體系 (MiLB 2A)", "pos": "pitcher","bat_throw": "左右投右打"},
        "潘文輝": {"id": "808207", "official_link": "https://www.milb.com/player/wen-hui-pan-808207", "team": "費城費城人體系 (MiLB 2A)", "pos": "pitcher","bat_throw": "右投右打"},
        "林振瑋": {"id": "813820", "official_link": "https://www.milb.com/player/chen-wei-lin-813820", "team": "聖路易紅雀體系 (MiLB 2A)", "pos": "pitcher","bat_throw": "右投右打"},
        "林維恩": {"id": "827734", "official_link": "https://www.milb.com/player/wei-en-lin-827734", "team": "奧克蘭運動家體系 (MiLB 2A)", "pos": "pitcher","bat_throw": "左投左打"},
        "張弘稜": {"id": "800213", "official_link": "https://www.milb.com/player/hung-leng-chang-800213", "team": "匹茲堡海盜體系 (MiLB A+)", "pos": "pitcher","bat_throw": "右投右打"},
        "沙子宸": {"id": "809223", "official_link": "https://www.milb.com/player/tzu-chen-sha-809223", "team": "奧克蘭運動家體系 (MiLB A+)", "pos": "pitcher","bat_throw": "右投右打"},
        "林盛恩": {"id": "806823", "official_link": "https://www.milb.com/player/sheng-en-lin-806823", "team": "辛辛那提紅人體系 (MiLB A)", "pos": "pitcher","bat_throw": "左投右打"},
        "沈家羲": {"id": "828430", "official_link": "https://www.milb.com/player/chia-shi-shen-828430", "team": "西雅圖水手體系 (MiLB A)", "pos": "pitcher","bat_throw": "右投右打"},
        "柯敬賢": {"id": "828667", "official_link": "https://www.milb.com/player/ching-hsien-ko-828667", "team": "洛杉磯道奇體系 (MiLB A)", "pos": "fielder","bat_throw": "左投右打"},
        "黃仲翔": {"id": "829473", "official_link": "https://www.milb.com/player/chung-hsiang-huang-829473", "team": "亞利桑那響尾蛇體系 (MiLB A)", "pos": "pitcher","bat_throw": "右投右打"},
        "李晨薰": {"id": "808486", "official_link": "https://www.milb.com/player/chen-hsun-lee-808486", "team": "舊金山巨人體系 (MiLB R)", "pos": "pitcher","bat_throw": "右投右打"},
        "陽念希": {"id": "806825", "official_link": "https://www.milb.com/player/nien-hsi-yang-806825", "team": "舊金山巨人體系 (MiLB R)", "pos": "pitcher","bat_throw": "左投右打"},
        "林鉑濬": {"id": "815458", "official_link": "https://www.google.com/search?q=%E6%9E%97%E9%89%91%E6%BF%AC+milb+stats", "team": "西雅圖水手體系 (MiLB R)", "pos": "pitcher","bat_throw": "左投右打"},
        "林張子俊": {"id": "815502", "official_link": "https://www.google.com/search?q=%E6%9E%97%E5%BC%B5%E5%AD%90%E4%BF%8A+milb+stats", "team": "密爾瓦基釀酒人體系 (MiLB R)", "pos": "pitcher","bat_throw": "右投左打"},
        "廖宥霖": {"id": "835879", "official_link": "https://www.milb.com/player/yu-lin-liao-835879", "team": "密爾瓦基釀酒人體系 (MiLB R)", "pos": "fielder","bat_throw": "右投右打"},
        "蘇嵐鴻": {"id": "815504", "official_link": "https://www.google.com/search?q=%E8%98%87%E5%B5%90%E9%B4%BB+milb+stats", "team": "聖地牙哥教士體系 (MiLB R)", "pos": "pitcher","bat_throw": "右投"}
    }
    
    # 2. 亞洲職棒官方數據與動態登錄
    asian_database = {
        "宋家豪": {"is_major": True, "official_link": "https://pacificleague.com/player/516123", "type": "pitcher", "team": "東北樂天金鷲 (NPB 一軍)", "position": "投手 (Pitcher)", "bat_throw": "右投右打"},
        "古林睿煬": {"is_major": False, "official_link": "https://pacificleague.com/player/525124", "type": "pitcher", "team": "北海道日本火腿鬥士 (NPB 二軍)", "position": "投手 (Pitcher)", "bat_throw": "右投右打"},
        "徐若熙": {"is_major": True, "official_link": "https://pacificleague.com/zh-CHT/player/526126", "type": "pitcher", "team": "福岡軟銀鷹 (NPB 一軍)", "position": "投手 (Pitcher)", "bat_throw": "右投右打"},
        "林安可": {"is_major": False, "official_link": "https://npb.jp/bis/players/33935152.html", "team": "埼玉西武獅 (NPB 二軍)", "position": "外野手 (Outfielder)", "bat_throw": "左投左打"},
        "陽岱鋼": {"is_major": False, "official_link": "https://npb.jp/bis/players/21825112.html", "team": "Oisix新潟天鵝之皇 (NPB 二軍)", "position": "外野手 (Outfielder)", "bat_throw": "右投右打"},
        "徐翔聖": {"is_major": False, "official_link": "https://www.google.com/search?q=%E5%BE%90%E7%BF%94%E8%81%96+%E6%97%A5%E8%81%B7+%E6%88%90%E7%B8%BE", "team": "東京養樂多燕子 (NPB 育成)", "position": "投手 (Pitcher)", "bat_throw": "右投右打","type": "pitcher"},
        "孫易磊": {"is_major": False, "official_link": "https://pacificleague.com/zh-CHT/player/524139", "team": "北海道日本火腿鬥士 (NPB 二軍)", "position": "投手 (Pitcher)", "bat_throw": "右投左打"},
        "黃錦豪": {"is_major": False, "official_link": "https://www.google.com/search?q=%E9%BB%83%E9%8C%A6%E8%B1%AA+%E6%97%A5%E8%81%B7+%E6%88%90%E7%B8%BE", "team": "讀賣巨人 (NPB 育成)", "position": "投手 (Pitcher)", "bat_throw": "左投左打","type": "pitcher"},
        "蕭齊": {"is_major": False, "official_link": "https://pacificleague.com/zh-CHT/player/525126", "team": "東北樂天金鷲 (NPB 育成)", "position": "投手 (Pitcher)", "bat_throw": "右投右打"},
        "林冠臣": {"is_major": False, "official_link": "https://pacificleague.com/zh-CHT/player/525117", "team": "埼玉西武獅 (NPB 二軍)", "position": "外野手 (Outfielder)", "bat_throw": "右投右打"},
        "陽柏翔": {"is_major": False, "official_link": "https://pacificleague.com/zh-CHT/player/525112", "team": "東北樂天金鷲 (NPB 育成)", "position": "內野手 (Infielder)", "bat_throw": "右投左打"},
        "陳睦衡": {"is_major": False, "official_link": "https://pacificleague.com/zh-CHT/player/525127", "team": "歐力士猛牛 (NPB 育成)", "position": "投手 (Pitcher)", "bat_throw": "右投左打"},
        "張峻瑋": {"is_major": False, "official_link": "https://pacificleague.com/zh-CHT/player/525128", "team": "福岡軟銀鷹 (NPB 育成)", "position": "投手 (Pitcher)", "bat_throw": "右投右打"},
        "林家正": {"is_major": False, "official_link": "https://www.google.com/search?q=%E6%9E%97%E5%AE%B6%E6%AD%A3+%E6%97%A5%E8%81%B7+%E6%88%90%E7%B8%BE", "team": "北海道日本火腿鬥士 (NPB 二軍)", "position": "捕手 (Catcher)", "bat_throw": "右投右打"},
        "王彥程": {"is_major": True, "official_link": "https://www.koreabaseball.com/Record/Player/PitcherDetail/Basic.aspx?playerId=56719", "team": "韓華鷹 (KBO Hanwha Eagles)", "position": "投手 (Pitcher)", "bat_throw": "左投左打"}
    }
    if name == "王彥程":
        stats = fetch_kbo_stats("56719")
        res = asian_database[name].copy()
        
        # 關鍵修正：補上這個 type，這樣前端的 if 判斷才會進到 "pitcher" 區塊
        res['type'] = 'pitcher'
        
        if stats:
            res.update(stats)
        else:
            # 若爬取失敗，提供預設值且確保欄位名稱正確
            res.update({"era": "0.00", "so": "0", "ip": "0.0", "w_l": "0勝-0敗"})
            
        return jsonify({"success": True, "data": res})
    
    if name == "林安可":
        stats = fetch_lin_stats() 
        res = {
            "name": "林安可",
            "league": "JPN",
            "type": "fielder",
            "position": "外野手 (Outfielder)",  # <--- 新增這行
            "team": "埼玉西武獅 (NPB 二軍)", 
            "official_link": "https://npb.jp/bis/players/33935152.html",
            "avg": stats.get('avg', '--'),
            "hr": stats.get('hr', '--'),
            "rbi": stats.get('rbi', '--'),
            "h_ab": stats.get('h_ab', '--'),
            "bat_throw": "左投左打"             
        }
        return jsonify({"success": True, "data": res})

    # 處理其他日職球員
    if name in npb_ids:
        p_type = asian_database[name].get('type', 'pitcher')
        stats = fetch_npb_stats(npb_ids[name], player_type=p_type)
        res = asian_database[name].copy()
        res['league'] = 'JPN'
        res['name'] = name
        res['type'] = p_type
        if stats:
            res.update(stats)
        return jsonify({"success": True, "data": res})
    # 特殊名單處理 (顯示 --)
    special_players = ["林鉑濬", "林張子俊", "蘇嵐鴻", "林家正", "黃錦豪", "徐翔聖", "陽岱鋼"]
    
    # 邏輯處理
 # ... 在 get_player_data 內 ...
    if name in mlb_database:
        player_config = mlb_database[name]
        is_minor = "MiLB" in player_config["team"]
        
        # 1. 特殊名單直接跳過爬蟲
        if name in ["林鉑濬", "林張子俊", "蘇嵐鴻"]: # 這些人都是投手
            res = {
        "name": name, # 確保補上名字
        "position": "投手 (Pitcher)", # 補上守備位置
        "type": "pitcher",           # 補上 type，這會觸發前端的 pitcher 介面
        "bat_throw": "-", 
        "team": player_config["team"], 
        "official_link": player_config["official_link"], 
        "is_major": False,
        "era": "--", "so": "--", "ip": "--", "w_l": "--" # 確保數據顯示為 --
        }
        # 2. 其他小聯盟球員執行爬蟲
        elif is_minor:
            stats = fetch_milb_stats(player_config["official_link"])
            res = {
                "position": "投手 (Pitcher)" if player_config["pos"] == "pitcher" else "野手 (Fielder)",
                "team": player_config["team"],
                "official_link": player_config["official_link"],
                "bat_throw": player_config.get("bat_throw", "-"), # <--- 在這裡補上這行
                "is_major": True 
            }
            if stats: res.update(stats)
            else: res.update({"era": "N/A", "so": "N/A", "ip": "N/A", "w_l": "N/A"})
            
        # 3. 原有 MLB 一軍邏輯
        else:
            res = fetch_mlb_stats(player_config["id"])
            res.update({"team": player_config["team"], "official_link": player_config["official_link"]})
            
        return jsonify({"success": True, "data": res})
    elif name in asian_database:
        res = asian_database[name].copy()
        res['league'] = 'JPN'
        res['name'] = name # 務必確保補上 name 欄位
        
        # 關鍵修正：確保 type 被正確傳遞到前端
        p_type = res.get('type', 'pitcher') 
        
        # 僅對非特殊名單球員執行爬蟲
        if name not in special_players: 
            stats = fetch_npb_stats(npb_ids.get(name), player_type=p_type)
            if stats: 
                res.update(stats)
            
        return jsonify({"success": True, "data": res})
    
    return jsonify({"success": False, "message": "資料庫無此球員"})
if __name__ == '__main__':
    app.run(debug=True)