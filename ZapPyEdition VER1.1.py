import ctypes
import os
import sys
import time
import threading
import subprocess
import itertools
import glob
import re
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import requests

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
print(f"рабочая директория: {os.getcwd()}")


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    if is_admin():
        return True
    script = os.path.abspath(sys.argv[0])
    params = " ".join(sys.argv[1:])
    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}" {params}', None, 1
        )
        
        if int(result) > 32:
            return False 
    except Exception as e:
        print(f"ошибка при запросе прав: {e}")
    print("ошибка: без прав администратора подбор невозможен.")
    #input("\nНажмите Enter для выхода...")
    sys.exit(1)


#константы
CONFIG_DIR = "GENERATEDCONFIGS"
TEST_URL = "https://static.rutracker.cc/favicon.ico"
MIN_SPEED_KBPS = 50.0

#быстрый базовый режим
BASE_MODES = ["fake,multisplit", "fake,split", "split", "disorder"]
BASE_SPLITS = ["1", "2", "mame"]
BASE_FOOLINGS = ["ts", "badsum"]
BASE_REPEATS = ["6", "11"]
BASE_TTLS = ["0"]

#медленный глубокий режим
DEEP_MODES = ["fake,multisplit", "fake,split", "split", "multisplit", "disorder", "fake,disorder", "fake", "syndrop"]
DEEP_SPLITS = ["1", "2", "3", "4", "mame", "host", "681", "1220", "1410"]  
DEEP_FOOLINGS = ["ts", "md5sig", "badsum", "none"]
DEEP_REPEATS = ["6", "8", "11", "15"]
DEEP_TTLS = ["0", "3", "4", "5", "6", "7"]

class UltraZapretConfigurator:
    def __init__(self, root):
        self.root = root
        self.root.title("In the honor of Flowseal! Zapret Auto Configurator v1.1")
        self.root.geometry("950x650")
        self.root.minsize(850, 550)
        
        self.is_running = False
        self.current_process = None
        
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR)
            
        self.setup_ui()
        
    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        control_frame = ttk.LabelFrame(main_frame, text="Главная панель", padding="10")
        control_frame.pack(fill=tk.X, pady=5)
        
        self.btn_start = ttk.Button(control_frame, text="Запустить Смарт-Подбор", command=lambda: self.start_work_thread(deep_only=False))
        self.btn_start.pack(side=tk.LEFT, padx=5, ipady=3)
        
        self.btn_deep_start = ttk.Button(control_frame, text="Принудительный долгий подбор", command=lambda: self.start_work_thread(deep_only=True))
        self.btn_deep_start.pack(side=tk.LEFT, padx=5, ipady=3)
        
        self.btn_stop = ttk.Button(control_frame, text="Остановить", state=tk.DISABLED, command=self.stop_tasks)
        self.btn_stop.pack(side=tk.LEFT, padx=5, ipady=3)
        
        self.btn_manage = ttk.Button(control_frame, text="📂 База конфигов", command=self.open_existing_menu)
        self.btn_manage.pack(side=tk.RIGHT, padx=5, ipady=3)
        
        status_frame = ttk.Frame(main_frame, padding="5")
        status_frame.pack(fill=tk.X, pady=5)
        
        self.lbl_status = ttk.Label(status_frame, text="Статус: Готов к сканированию", font=("Segoe UI", 10, "bold"))
        self.lbl_status.pack(side=tk.LEFT, padx=5)
        
        self.progress_bar = ttk.Progressbar(status_frame, mode='indeterminate', length=150)
        
        log_frame = ttk.LabelFrame(main_frame, text="ЛОГ", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 9), bg="#141414", fg="#dedede")
        self.log_area.pack(fill=tk.BOTH, expand=True)
        
        self.log_area.tag_config('success', foreground='#a6e22e', font=("Consolas", 9, "bold"))
        self.log_area.tag_config('error', foreground='#f92672')
        self.log_area.tag_config('info', foreground='#66d9ef')
        self.log_area.tag_config('warn', foreground='#fd971f')
        
        self.log("система готова.", "info")

    def log(self, message, tag=None):
        def append():
            self.log_area.configure(state=tk.NORMAL)
            self.log_area.insert(tk.END, time.strftime("[%H:%M:%S] ") + message + "\n", tag)
            self.log_area.configure(state=tk.DISABLED)
            self.log_area.see(tk.END)
        self.root.after(0, append)

    def set_status(self, text):
        self.root.after(0, lambda: self.lbl_status.config(text=f"Статус: {text}"))

    def force_kill_winws(self):
        if sys.platform == "win32":
            subprocess.run("taskkill /f /im winws.exe", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)

    def check_download_speed(self):
        start_time = time.time()
        downloaded_bytes = 0
        
        try:
            session = requests.Session()
            session.trust_env = False 
            
            response = session.get(TEST_URL, stream=True, timeout=(1.2, 1.5))
            if response.status_code != 200:
                return False, 0.0
                
            for chunk in response.iter_content(chunk_size=8192):
                if not self.is_running:
                    return False, 0.0
                downloaded_bytes += len(chunk)
                
                if time.time() - start_time > 1.2:
                    break
                    
            duration = time.time() - start_time
            if duration <= 0:
                return False, 0.0
                
            speed_kbps = (downloaded_bytes * 8) / (duration * 1000)
            return speed_kbps >= MIN_SPEED_KBPS, speed_kbps
            
        except Exception:
            return False, 0.0

    def generate_bat_content(self, desync, split_pos, fooling, repeat, ttl):
        ttl_cmd = f"--dpi-desync-ttl={ttl}" if ttl != "0" else ""
        content = f"""@echo off
chcp 65001 > nul
:: 65001 - UTF-8

cd /d "%~dp0"
cd /d ..\\
call service.bat status_zapret
call service.bat check_updates
call service.bat load_game_filter
call service.bat load_user_lists
echo:

set "BIN=%~dp0..\\bin\\"
set "LISTS=%~dp0..\\lists\\"
cd /d %BIN%

start "zapret: %~n0" /min "%BIN%winws.exe" --wf-tcp=80,443,2053,2083,2087,2096,8443,%GameFilterTCP% --wf-udp=443,19294-19344,50000-50100,%GameFilterUDP% ^
--filter-udp=443 --hostlist="%LISTS%list-general.txt" --hostlist="%LISTS%list-general-user.txt" --hostlist-exclude="%LISTS%list-exclude.txt" --hostlist-exclude="%LISTS%list-exclude-user.txt" --ipset-exclude="%LISTS%ipset-exclude.txt" --ipset-exclude="%LISTS%ipset-exclude-user.txt" --dpi-desync=fake --dpi-desync-repeats=11 --dpi-desync-fake-quic="%BIN%quic_initial_www_google_com.bin" --new ^
--filter-udp=19294-19344,50000-50100 --filter-l7=discord,stun --dpi-desync=fake --dpi-desync-fake-discord="%BIN%quic_initial_dbankcloud_ru.bin" --dpi-desync-fake-stun="%BIN%quic_initial_dbankcloud_ru.bin" --dpi-desync-repeats=6 --new ^
--filter-tcp=2053,2083,2087,2096,8443 --hostlist-domains=discord.media --dpi-desync={desync} --dpi-desync-split-seqovl=681 --dpi-desync-split-pos={split_pos} --dpi-desync-fooling={fooling} --dpi-desync-repeats={repeat} {ttl_cmd} --dpi-desync-split-seqovl-pattern="%BIN%tls_clienthello_www_google_com.bin" --dpi-desync-fake-tls-mod=rnd,dupsid,sni=www.google.com --new ^
--filter-tcp=443 --hostlist="%LISTS%list-google.txt" --ip-id=zero --dpi-desync={desync} --dpi-desync-split-seqovl=681 --dpi-desync-split-pos={split_pos} --dpi-desync-fooling={fooling} --dpi-desync-repeats={repeat} {ttl_cmd} --dpi-desync-split-seqovl-pattern="%BIN%tls_clienthello_www_google_com.bin" --dpi-desync-fake-tls-mod=rnd,dupsid,sni=www.google.com --new ^
--filter-tcp=80,443 --hostlist="%LISTS%list-general.txt" --hostlist="%LISTS%list-general-user.txt" --hostlist-exclude="%LISTS%list-exclude.txt" --hostlist-exclude="%LISTS%list-exclude-user.txt" --ipset-exclude="%LISTS%ipset-exclude.txt" --ipset-exclude="%LISTS%ipset-exclude-user.txt" --dpi-desync={desync} --dpi-desync-split-seqovl=681 --dpi-desync-split-pos={split_pos} --dpi-desync-fooling={fooling} --dpi-desync-repeats={repeat} {ttl_cmd} --dpi-desync-split-seqovl-pattern="%BIN%tls_clienthello_www_google_com.bin" --dpi-desync-fake-tls-mod=rnd,dupsid,sni=www.google.com --dpi-desync-fake-http="%BIN%tls_clienthello_max_ru.bin" --new ^
--filter-udp=443 --ipset="%LISTS%ipset-all.txt" --hostlist-exclude="%LISTS%list-exclude.txt" --hostlist-exclude="%LISTS%list-exclude-user.txt" --ipset-exclude="%LISTS%ipset-exclude.txt" --ipset-exclude="%LISTS%ipset-exclude-user.txt" --dpi-desync=fake --dpi-desync-repeats=11 --dpi-desync-fake-quic="%BIN%quic_initial_www_google_com.bin" --new ^
--filter-tcp=80,443,8443 --ipset="%LISTS%ipset-all.txt" --hostlist-exclude="%LISTS%list-exclude.txt" --hostlist-exclude="%LISTS%list-exclude-user.txt" --ipset-exclude="%LISTS%ipset-exclude.txt" --ipset-exclude="%LISTS%ipset-exclude-user.txt" --dpi-desync={desync} --dpi-desync-split-seqovl=681 --dpi-desync-split-pos={split_pos} --dpi-desync-fooling={fooling} --dpi-desync-repeats={repeat} {ttl_cmd} --dpi-desync-split-seqovl-pattern="%BIN%tls_clienthello_www_google_com.bin" --dpi-desync-fake-tls-mod=rnd,dupsid,sni=www.google.com --dpi-desync-fake-http="%BIN%tls_clienthello_max_ru.bin" --new ^
--filter-tcp=%GameFilterTCP% --ipset="%LISTS%ipset-all.txt" --ipset-exclude="%LISTS%ipset-exclude.txt" --ipset-exclude="%LISTS%ipset-exclude-user.txt" --dpi-desync={desync} --dpi-desync-any-protocol=1 --dpi-desync-cutoff=n4 --dpi-desync-split-seqovl=681 --dpi-desync-split-pos={split_pos} --dpi-desync-fooling={fooling} --dpi-desync-repeats={repeat} {ttl_cmd} --dpi-desync-split-seqovl-pattern="%BIN%tls_clienthello_www_google_com.bin" --dpi-desync-fake-tls-mod=rnd,dupsid,sni=www.google.com --dpi-desync-fake-http="%BIN%tls_clienthello_max_ru.bin" --new ^
--filter-udp=%GameFilterUDP% --ipset="%LISTS%ipset-all.txt" --ipset-exclude="%LISTS%ipset-exclude.txt" --ipset-exclude="%LISTS%ipset-exclude-user.txt" --dpi-desync=fake --dpi-desync-repeats=10 --dpi-desync-any-protocol=1 --dpi-desync-fake-unknown-udp="%BIN%quic_initial_dbankcloud_ru.bin" --dpi-desync-cutoff=n3
"""
        return content

    def build_exec_arguments(self, desync, split_pos, fooling, repeat, ttl):
        bin_path = os.path.abspath("bin")
        lists_path = os.path.abspath("lists")
        game_tcp = "19294,19344"
        game_udp = "19294-19344,50000-50100"
        
        ttl_list = [f"--dpi-desync-ttl={ttl}"] if ttl != "0" else []
        
        args = [os.path.join(bin_path, "winws.exe"), f"--wf-tcp=80,443,2053,2083,2087,2096,8443,{game_tcp}", f"--wf-udp=443,19294-19344,50000-50100,{game_udp}",
            "--filter-udp=443", f"--hostlist={lists_path}\\list-general.txt", f"--hostlist={lists_path}\\list-general-user.txt", f"--hostlist-exclude={lists_path}\\list-exclude.txt", f"--hostlist-exclude={lists_path}\\list-exclude-user.txt", f"--ipset-exclude={lists_path}\\ipset-exclude.txt", f"--ipset-exclude={lists_path}\\ipset-exclude-user.txt", "--dpi-desync=fake", "--dpi-desync-repeats=11", f"--dpi-desync-fake-quic={bin_path}\\quic_initial_www_google_com.bin", "--new",
            "--filter-udp=19294-19344,50000-50100", "--filter-l7=discord,stun", "--dpi-desync=fake", f"--dpi-desync-fake-discord={bin_path}\\quic_initial_dbankcloud_ru.bin", f"--dpi-desync-fake-stun={bin_path}\\quic_initial_dbankcloud_ru.bin", "--dpi-desync-repeats=6", "--new",
            "--filter-tcp=2053,2083,2087,2096,8443", "--hostlist-domains=discord.media", f"--dpi-desync={desync}", "--dpi-desync-split-seqovl=681", f"--dpi-desync-split-pos={split_pos}", f"--dpi-desync-fooling={fooling}", f"--dpi-desync-repeats={repeat}"] + ttl_list + [f"--dpi-desync-split-seqovl-pattern={bin_path}\\tls_clienthello_www_google_com.bin", f"--dpi-desync-fake-tls-mod=rnd,dupsid,sni=www.google.com", "--new",
            "--filter-tcp=443", f"--hostlist={lists_path}\\list-google.txt", "--ip-id=zero", f"--dpi-desync={desync}", "--dpi-desync-split-seqovl=681", f"--dpi-desync-split-pos={split_pos}", f"--dpi-desync-fooling={fooling}", f"--dpi-desync-repeats={repeat}"] + ttl_list + [f"--dpi-desync-split-seqovl-pattern={bin_path}\\tls_clienthello_www_google_com.bin", f"--dpi-desync-fake-tls-mod=rnd,dupsid,sni=www.google.com", "--new",
            "--filter-tcp=80,443", f"--hostlist={lists_path}\\list-general.txt", f"--hostlist={lists_path}\\list-general-user.txt", f"--hostlist-exclude={lists_path}\\list-exclude.txt", f"--hostlist-exclude={lists_path}\\list-exclude-user.txt", f"--ipset-exclude={lists_path}\\ipset-exclude.txt", f"--ipset-exclude={lists_path}\\ipset-exclude-user.txt", f"--dpi-desync={desync}", "--dpi-desync-split-seqovl=681", f"--dpi-desync-split-pos={split_pos}", f"--dpi-desync-fooling={fooling}", f"--dpi-desync-repeats={repeat}"] + ttl_list + [f"--dpi-desync-split-seqovl-pattern={bin_path}\\tls_clienthello_www_google_com.bin", f"--dpi-desync-fake-tls-mod=rnd,dupsid,sni=www.google.com", f"--dpi-desync-fake-http={bin_path}\\tls_clienthello_max_ru.bin", "--new",
            "--filter-udp=443", f"--ipset={lists_path}\\ipset-all.txt", f"--hostlist-exclude={lists_path}\\list-exclude.txt", f"--hostlist-exclude={lists_path}\\list-exclude-user.txt", f"--ipset-exclude={lists_path}\\ipset-exclude.txt", f"--ipset-exclude={lists_path}\\ipset-exclude-user.txt", "--dpi-desync=fake", "--dpi-desync-repeats=11", f"--dpi-desync-fake-quic={bin_path}\\quic_initial_www_google_com.bin", "--new",
            "--filter-tcp=80,443,8443", f"--ipset={lists_path}\\ipset-all.txt", f"--hostlist-exclude={lists_path}\\list-exclude.txt", f"--hostlist-exclude={lists_path}\\list-exclude-user.txt", f"--ipset-exclude={lists_path}\\ipset-exclude.txt", f"--ipset-exclude={lists_path}\\ipset-exclude-user.txt", f"--dpi-desync={desync}", "--dpi-desync-split-seqovl=681", f"--dpi-desync-split-pos={split_pos}", f"--dpi-desync-fooling={fooling}", f"--dpi-desync-repeats={repeat}"] + ttl_list + [f"--dpi-desync-split-seqovl-pattern={bin_path}\\tls_clienthello_www_google_com.bin", f"--dpi-desync-fake-tls-mod=rnd,dupsid,sni=www.google.com", f"--dpi-desync-fake-http={bin_path}\\tls_clienthello_max_ru.bin", "--new",
            f"--filter-tcp={game_tcp}", f"--ipset={lists_path}\\ipset-all.txt", f"--ipset-exclude={lists_path}\\ipset-exclude.txt", f"--ipset-exclude={lists_path}\\ipset-exclude-user.txt", f"--dpi-desync={desync}", "--dpi-desync-any-protocol=1", "--dpi-desync-cutoff=n4", "--dpi-desync-split-seqovl=681", f"--dpi-desync-split-pos={split_pos}", f"--dpi-desync-fooling={fooling}", f"--dpi-desync-repeats={repeat}"] + ttl_list + [f"--dpi-desync-split-seqovl-pattern={bin_path}\\tls_clienthello_www_google_com.bin", f"--dpi-desync-fake-tls-mod=rnd,dupsid,sni=www.google.com", f"--dpi-desync-fake-http={bin_path}\\tls_clienthello_max_ru.bin", "--new",
            f"--filter-udp={game_udp}", f"--ipset={lists_path}\\ipset-all.txt", f"--ipset-exclude={lists_path}\\ipset-exclude.txt", f"--ipset-exclude={lists_path}\\ipset-exclude-user.txt", "--dpi-desync=fake", "--dpi-desync-repeats=10", "--dpi-desync-any-protocol=1", f"--dpi-desync-fake-unknown-udp={bin_path}\\quic_initial_dbankcloud_ru.bin", "--dpi-desync-cutoff=n3"]
        return args

    def start_work_thread(self, deep_only=False):
        if not os.path.isdir("bin") or not os.path.exists("bin\\winws.exe"):
            messagebox.showerror("Ошибка", "Скрипт должен лежать в главной папке zapret рядом с bin\\")
            return
        self.is_running = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_deep_start.config(state=tk.DISABLED)
        self.btn_manage.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.progress_bar.pack(side=tk.LEFT, padx=10)
        self.progress_bar.start(10)
        
        threading.Thread(target=self.core_orchestrator, args=(deep_only,), daemon=True).start()

    def core_orchestrator(self, deep_only=False):
        existing = glob.glob(os.path.join(CONFIG_DIR, "*.bat"))
        nums = [int(re.match(r"(\d+)\.bat", os.path.basename(f)).group(1)) for f in existing if re.match(r"(\d+)\.bat", os.path.basename(f))]
        self.next_index = max(nums) + 1 if nums else 1

        if deep_only:
            self.log("--- ЗАПУСК ПРИНУДИТЕЛЬНОГО ПОЛНОГО СКАНА(это надолго) ---", "warn")
            deep_combos = self.build_smart_pool(DEEP_MODES, DEEP_SPLITS, DEEP_FOOLINGS, DEEP_REPEATS, DEEP_TTLS)
            self.execute_pool(deep_combos, "Глубокий тест")
        else:
            self.log("--- СТАРТ ЭТАПА 1: СВЕРХБЫСТРЫЙ БАЗОВЫЙ ПОДБОР ---", "info")
            self.log("--- ЕСЛИ ЭТО НЕ СРАБОТАЕТ ТО БУДЕТ ПУЩЕН ПОЛНЫЙ СКАН")
            base_combos = self.build_smart_pool(BASE_MODES, BASE_SPLITS, BASE_FOOLINGS, BASE_REPEATS, BASE_TTLS)
            success_in_base = self.execute_pool(base_combos, "Базовый тест")

            if success_in_base == 0:
                self.log("Базовые стратегии не сработали. Автоматически включаем DEEP SCAN...", "warn")
                deep_combos = self.build_smart_pool(DEEP_MODES, DEEP_SPLITS, DEEP_FOOLINGS, DEEP_REPEATS, DEEP_TTLS)
                self.execute_pool(deep_combos, "Глубокий тест")
            else:
                self.log(f"На быстром этапе найдено {success_in_base} рабочих стратегий!", "success")

        self.stop_tasks()

    def build_smart_pool(self, modes, splits, foolings, repeats, ttls):
        raw_product = itertools.product(modes, splits, foolings, repeats, ttls)
        optimized_pool = []
        for desync, split_pos, fooling, repeat, ttl in raw_product:
            if "fake" not in desync and repeat != "6": continue
            if "split" not in desync and split_pos != "1": continue
            optimized_pool.append((desync, split_pos, fooling, repeat, ttl))
        return optimized_pool

    def execute_pool(self, pool, stage_name):
        total = len(pool)
        success_count = 0

        for idx, (desync, split_pos, fooling, repeat, ttl) in enumerate(pool, start=1):
            if not self.is_running: break
            self.set_status(f"{stage_name}: {idx}/{total} | Найдено: {success_count}")
            
            self.force_kill_winws()
            time.sleep(0.15)
            
            args = self.build_exec_arguments(desync, split_pos, fooling, repeat, ttl)
            try:
                self.current_process = subprocess.Popen(
                    args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=0x08000000 if sys.platform == "win32" else 0
                )
            except Exception as e:
                self.log(f"Ошибка вызова winws: {e}", "error")
                continue
                
            time.sleep(0.8)
            is_valid, speed = self.check_download_speed()
            
            if self.current_process:
                self.current_process.terminate()
                self.current_process.wait()
                self.current_process = None
                
            if is_valid:
                success_count += 1
                ttl_info = f" | TTL: {ttl}" if ttl != "0" else ""
                self.log(f"🔥 [{stage_name}] РАБОТАЕТ! {desync} | Split: {split_pos}{ttl_info} -> {speed:.1f} кбит/с", "success")
                
                bat_path = os.path.join(CONFIG_DIR, f"{self.next_index}.bat")
                bat_data = self.generate_bat_content(desync, split_pos, fooling, repeat, ttl)
                try:
                    with open(bat_path, "w", encoding="utf-8") as bf:
                        bf.write(bat_data)
                    self.next_index += 1
                except Exception as e:
                    self.log(f"Запись файла сорвалась: {e}", "error")
            else:
                if speed == 0:
                    self.log(f"[-] Combo {idx}: Блокировка / Отказ сети")
                else:
                    self.log(f"[~] Combo {idx}: Низкая скорость ({speed:.1f} kbps)", "warn")
        return success_count

    def stop_tasks(self):
        self.is_running = False
        if self.current_process:
            try:
                self.current_process.terminate()
                self.current_process.wait()
            except: pass
            self.current_process = None
        self.force_kill_winws()
        self.root.after(0, self.reset_ui)

    def reset_ui(self):
        self.btn_start.config(state=tk.NORMAL)
        self.btn_deep_start.config(state=tk.NORMAL)
        self.btn_manage.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.set_status("Ожидание")


    #ОКНО УПРАВЛЕНИЯ БАТНИКАМИ !НЕ ТРОГАТЬ!

    def open_existing_menu(self):
        files = glob.glob(os.path.join(CONFIG_DIR, "*.bat"))
        if not files:
            messagebox.showinfo("Инфо", "Папка GENERATEDCONFIGS пуста.")
            return
            
        files.sort(key=lambda x: int(re.search(r"(\d+)\.bat$", x).group(1)) if re.search(r"(\d+)\.bat$", x) else 9999)

        self.menu_win = tk.Toplevel(self.root)
        self.menu_win.title("База ваших конфигов")
        self.menu_win.geometry("550x500")
        self.menu_win.grab_set()
        
        list_frame = ttk.Frame(self.menu_win, padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(list_frame, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.checkbox_vars = {}
        self.row_frames = {}
        self.status_labels = {}
        self.file_paths = {}
        
        for filename in [os.path.basename(f) for f in files]:
            row_f = tk.Frame(scrollable_frame, bg="#ffffff", bd=1, relief=tk.RIDGE, padx=5, pady=2)
            row_f.pack(fill=tk.X, expand=True, pady=2, ipady=3)
            
            var = tk.BooleanVar(value=True)
            chk = tk.Checkbutton(row_f, text=filename, variable=var, bg="#ffffff", anchor="w")
            chk.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            lbl_stat = tk.Label(row_f, text="Готов к проверке", font=("Segoe UI", 9, "italic"), fg="#7f8c8d", bg="#ffffff", width=18, anchor="e")
            lbl_stat.pack(side=tk.RIGHT, padx=10)
            
            self.checkbox_vars[filename] = var
            self.row_frames[filename] = row_f
            self.status_labels[filename] = lbl_stat
            self.file_paths[filename] = os.path.join(CONFIG_DIR, filename)
            
        btn_frame = ttk.Frame(self.menu_win, padding="10")
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        ttk.Button(btn_frame, text="Выбрать все", command=lambda: [v.set(True) for v in self.checkbox_vars.values()]).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Снять все", command=lambda: [v.set(False) for v in self.checkbox_vars.values()]).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Отмена", command=self.menu_win.destroy).pack(side=tk.RIGHT, padx=5)
        
        self.btn_menu_test = ttk.Button(btn_frame, text="🔥 Перепроверить", command=self.start_existing_verification)
        self.btn_menu_test.pack(side=tk.RIGHT, padx=5)

    def start_existing_verification(self):
        self.is_running = True
        self.btn_menu_test.config(state=tk.DISABLED)
        threading.Thread(target=self.verification_loop, daemon=True).start()

    def parse_arguments_from_bat(self, filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            clean_content = content.replace("^\n", " ").replace("^\r\n", " ")
            
            match_line = re.search(r'--hostlist-domains=discord\.media\s+(.*)', clean_content)
            if not match_line:
                return None
                
            target_str = match_line.group(1)
            
            desync_m = re.search(r'--dpi-desync=([\w,]+)', target_str)
            split_m = re.search(r'--dpi-desync-split-pos=([\w]+)', target_str)
            fooling_m = re.search(r'--dpi-desync-fooling=([\w]+)', target_str)
            repeat_m = re.search(r'--dpi-desync-repeats=(\d+)', target_str)
            ttl_m = re.search(r'--dpi-desync-ttl=(\d+)', target_str)
            
            if not (desync_m and split_m and fooling_m and repeat_m):
                return None
                
            desync = desync_m.group(1)
            split_pos = split_m.group(1)
            fooling = fooling_m.group(1)
            repeat = repeat_m.group(1)
            ttl = ttl_m.group(1) if ttl_m else "0"
            
            return self.build_exec_arguments(desync, split_pos, fooling, repeat, ttl)
        except Exception as e:
            self.log(f"Не удалось распарсить {os.path.basename(filepath)}: {e}", "error")
            return None

    def verification_loop(self):
        self.log("=== Перепроверка сохранённой базы конфигов ===", "info")
        targets = [name for name, var in self.checkbox_vars.items() if var.get()]
        
        for name in targets:
            if not self.is_running: break
            
            self.root.after(0, lambda n=name: self.status_labels[n].config(text="Замер...", fg="#d35400"))
            self.force_kill_winws()
            time.sleep(0.2)
            
            args = self.parse_arguments_from_bat(self.file_paths[name])
            if not args: 
                self.log(f"Ошибка чтения структуры в {name}, пропускаем", "error")
                self.root.after(0, lambda n=name: self.status_labels[n].config(text="Ошибка структуры", fg="#c0392b"))
                continue
            
            try:
                self.current_process = subprocess.Popen(
                    args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, 
                    creationflags=0x08000000 if sys.platform == "win32" else 0
                )
            except: 
                continue
                
            time.sleep(0.8)
            is_valid, speed = self.check_download_speed()
            
            if self.current_process:
                self.current_process.terminate()
                self.current_process.wait()
                self.current_process = None
                
            if is_valid:
                self.log(f"Конфиг {name} работает со скоростью {speed:.1f} кбит/с", "success")
                self.root.after(0, lambda n=name, s=speed: self.update_row_ui(n, True, f"ОК ({int(s)} kbps)"))
            else:
                self.log(f"Конфиг {name} НЕ ПРОШЕЛ ТЕСТ. Удаление файла.", "error")
                self.root.after(0, lambda n=name: self.update_row_ui(n, False, "Удален"))
                try: 
                    os.remove(self.file_paths[name])
                except Exception as e: 
                    self.log(f"Не удалось физически удалить файл {name}: {e}", "error")
                
        self.force_kill_winws()
        self.is_running = False
        self.root.after(0, lambda: self.btn_menu_test.config(state=tk.NORMAL) if hasattr(self, 'btn_menu_test') and self.btn_menu_test.winfo_exists() else None)

    def update_row_ui(self, name, success, text):
        if success:
            self.row_frames[name].config(bg="#e8f8f5")
            self.status_labels[name].config(text=text, fg="#27ae60", bg="#e8f8f5")
        else:
            self.row_frames[name].config(bg="#fce4d6")
            self.status_labels[name].config(text=text, fg="#c0392b", bg="#fce4d6")

if __name__ == "__main__":
    def on_closing():
        app.stop_tasks()
        root.destroy()
        sys.exit(0)
    if not is_admin():
        run_as_admin()
        sys.exit(0)

    root = tk.Tk()
    app = UltraZapretConfigurator(root)
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()