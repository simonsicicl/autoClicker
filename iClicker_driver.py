from json import load
from time import sleep

from datetime import datetime, timezone
from threading import Thread, Lock, Event
from typing import Union, List

from seleniumwire.request import Request, Response
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait
from seleniumwire import webdriver
from selenium.webdriver.chrome.service import Service
from timezonefinder import TimezoneFinder
import pytz

from course_info import HourMinute, course_info


class iClicker_driver:
    REQUEST_URL: str = 'https://api.iclicker.com/student/course/status'
    LOG_IN_URL: str = 'https://student.iclicker.com/#/login'
    COURSES_URL: str = 'https://student.iclicker.com/#/courses'
    JOIN_BTN_ID: str = 'btnJoin'

    def __init__(self, config_file: str = 'config.json', auto_wait: bool = True, driver_path: Union[str, None] = None):
        self.joinUp: bool = False
        seleniumwire_options = {
            'exclude_hosts': ['eum-us-west-2.instana.io',
                              'analytic.rollout.io',
                              'accounts.google.com',
                              'www.google-analytics.com',
                              'iclicker-prod-inst-analytics.macmillanlearning.com'],
            'ignore_http_methods': ['GET', 'HEAD', 'PUT', 'DELETE',
                                    'CONNECT', 'OPTIONS', 'TRACE',
                                    'PATCH']}
        from selenium.webdriver.chrome.options import Options
        chrome_options = Options()
        chrome_options.add_experimental_option('detach', True)
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        # You can add more options here if needed
        if driver_path is not None:
            self.driver: webdriver.Chrome = webdriver.Chrome(service=Service(driver_path),
                                                             seleniumwire_options=seleniumwire_options,
                                                             options=chrome_options)
        else:
            self.driver: webdriver.Chrome = webdriver.Chrome(seleniumwire_options=seleniumwire_options,
                                                             options=chrome_options)
        self.driver.response_interceptor = self.response_interceptor

        # Config info
        with open(config_file, 'r') as f:
            self.config: dict = load(f)
        self.account_name: str = ''

        self.auto_wait = auto_wait

        # For timing
        self.course_schedule: List[course_info] = []
        self.currentCourseIndex = -1
        self.nextCourseIndex = 0

        # Thread to wait to join up
        self.wait_thread: Thread = Thread(name='WaitForMeeting', target=self.wait_for_meeting)

        self.time_thread: Thread = Thread(name='CheckTime', target=self.wait_for_time)

        self.time_lock: Lock = Lock()  # Thread lock

        self.joinEvent: Event = Event()
        self.joinThreadIsWaitingEvent: Event = Event()
        self.joinThreadIsWaiting: bool = False
        self.restartEvent: Event = Event()
        self.restartFlag: bool = False
        self.currentCourse: str = ''
        self.latitude: float = 40.4293016
        self.longitude: float = -86.9126755
        self.set_geolocation(self.latitude, self.longitude)  # Default to MSEE

    def start(self, account_name: Union[str, None] = None):
        try:
            if not self.account_name:
                self.get_account(account_name)
        except ValueError:
            self.cmd_print('START', "Couldn't find email or password in config file. Not starting...")
        self.set_up_courses()
        self.driver.get(self.LOG_IN_URL)
        self.cmd_print('START', "Please complete the login manually in the browser window.")
        # Wait until login is successful (detect by presence of course page)
        while True:
            try:
                self.wait_for_element('.course-title', timeout=120)  # Increase timeout for SSO
                break
            except Exception:
                self.cmd_print('START', "Still waiting for login to complete...")
                sleep(2)
        self.cmd_print('START', 'Login complete!')
        self.time_thread.start()
    
    def cmd_print(self, funcname:str, msg: str, replace: bool = False):
        if replace:
            print(' ' * 80, end='\r')  # Clear the line
        else:
            print('\n', end='')
        print(f'{self.get_local_now().time().strftime("%H:%M:%S")} [{funcname}] {msg}', end='\r' if replace else '')

    def navigate_to_course(self, course: str):
        self.time_lock.acquire()
        self.cmd_print('NTC', f'Navigating to course {course}')
        # This XPath searches for the course button by the text contained within.
        # Unfortunately the buttons don't have descriptive IDs, so we have to use XPath
        WebDriverWait(self.driver, 20).until(
            ec.element_to_be_clickable((By.XPATH, f'//a[label[text() = \'{course}\']]'))).click()
        self.currentCourse = course
        del self.driver.requests
        if self.auto_wait:
            self.start_wait()
        self.time_lock.release()
        self.wait_thread.join()

    def start_wait(self):
        if not self.wait_thread.is_alive():
            self.wait_thread.start()

    def wait_for_meeting(self):
        while True:
            self.cmd_print('WFM', 'Waiting for meeting...')
            # 不斷偵測 btnJoin 是否出現
            btn_clicked = False
            while not btn_clicked:
                if self.course_schedule[self.currentCourseIndex].end_time <= HourMinute.utcnow(self.get_local_now()):
                    self.cmd_print('WFM', 'Current course has ended, stopping wait_for_meeting...')
                    return
                self.time_lock.acquire()
                try:
                    btn = self.driver.find_element(By.ID, self.JOIN_BTN_ID)
                    if btn.is_displayed() and btn.is_enabled():
                        self.cmd_print('WFM', 'Checking for btnJoin... btnJoin appeared and is clickable! Clicking...')
                        btn.click()
                        btn_clicked = True
                    else:
                        self.cmd_print('WFM', 'Checking for btnJoin... btnJoin not clickable yet.', replace=True)
                except Exception:
                    self.cmd_print('WFM', 'Checking for btnJoin... btnJoin not found yet.', replace=True)
                self.time_lock.release()
                sleep(5)
            # three-dot-loader
            try:
                WebDriverWait(self.driver, 20).until(
                    ec.invisibility_of_element((By.ID, 'three-dot-loader')))
            except Exception:
                self.cmd_print('WFM', 'Waiting for three-dot-loader to disappear...')
            self.cmd_print('WFM', 'Clicked btnJoin and finished join process.')
            self.joinThreadIsWaiting = True
            self.joinThreadIsWaitingEvent.set()
            self.cmd_print('WFM', 'Released time_lock. Waiting for restart flag...')
            # todo: add wait for event to restart
            while True:
                self.restartEvent.wait()
                self.time_lock.acquire()
                if self.restartFlag:
                    break
                self.time_lock.release()
            self.time_lock.acquire()
            self.restartFlag = False
            self.time_lock.release()
            self.cmd_print('WFM', 'Restart flag raised. wait_for_meeting is restarting...')

    def wait_for_time(self):
        next_course_time = self.course_schedule[self.nextCourseIndex].start_time
        self.cmd_print('WFT', f'Next course time is {next_course_time}')
        wait_for_next_day: bool = False
        current_day: int = self.get_local_now().weekday()
        while True:
            if wait_for_next_day:
                self.cmd_print('WFT', f'Need to wait for next day for course {self.course_schedule[self.nextCourseIndex].course}')
                while current_day == self.get_local_now().weekday():
                    self.cmd_print('WFT', 'waiting for next day...', replace=True)
                    sleep(60)
                wait_for_next_day = False
                self.cmd_print('WFT', 'No longer waiting for next day!')
            now = HourMinute.utcnow(self.get_local_now())
            self.cmd_print('WFT', 'waiting for time...')
            if now >= next_course_time:  # and now >= self.course_schedule[self.currentCourseIndex].end_time
                self.cmd_print('WFT', f'Time change! Entering the course {self.course_schedule[self.nextCourseIndex].course} which starts at {next_course_time}')
                if self.driver.current_url != self.COURSES_URL:
                    self.time_lock.acquire()
                    self.cmd_print('WFT', 'Switching to courses URL...')
                    self.driver.get(self.COURSES_URL)
                    self.time_lock.release()
                # print('Waiting for webpage to load')
                # self.wait_for_element('.course-title')
                # print(f"Done waiting. Navigating to course of {self.course_schedule[self.nextCourseIndex].course}")

                self.currentCourseIndex = self.nextCourseIndex

                self.navigate_to_course(self.course_schedule[self.nextCourseIndex].course)
                self.cmd_print('WFT', 'Done navigating.')
                
                self.time_lock.acquire()
                self.cmd_print('WFT', 'Switching to courses URL...')
                self.driver.get(self.COURSES_URL)

                # Setting up next course switch
                if self.nextCourseIndex == len(self.course_schedule) - 1:  # Loop the next course
                    self.nextCourseIndex = 0
                    wait_for_next_day = True  # Need to set this because [0] < [current] and likely < now
                    current_day = self.get_local_now().weekday()
                else:
                    self.nextCourseIndex += 1
                next_course_time = self.course_schedule[self.nextCourseIndex].start_time
                self.cmd_print('WFT', f'Next course switch to occur at {next_course_time}')
                self.cmd_print('WFT', 'Releasing time_lock')
                self.time_lock.release()
            else:
                sleep(60)

    def get_account(self, name: Union[str, None] = None):
        if name is None:
            self.account_name = input('Enter the account name to use (i.e., the account name in config.json)')
        else:
            self.account_name = name
        if self.account_name not in self.config or 'Email' not in self.config[self.account_name] or 'Password' not in \
                self.config[self.account_name]:
            raise ValueError("Could not find email or password in config file.")

    def wait_for_element(self, selector, timeout=30):
        WebDriverWait(self.driver, timeout).until(ec.presence_of_element_located((By.CSS_SELECTOR, selector)))

    def response_interceptor(self, request: Request, response: Response):
        if request.url == self.REQUEST_URL:
            body = response.body.decode()
            if self.joinUp:
                if body[63:67] == 'null':
                    self.joinUp = False
                    # return
            elif body[63:67] != 'null':
                self.joinUp = True
                self.joinEvent.set()
            else:
                file = open("HTTP_req.log", "a")
                from datetime import timezone
                file.write(f'-------------\n{self.get_local_now()}\n'
                           f'Request:\n{request.url}\n{request.body.decode("utf-8")}\n'
                           f'Response:\n{response.body.decode("utf-8")}')
                file.close()

    def set_up_courses(self):
        # 讀取所有課程
        for key, value in self.config[self.account_name]['Courses'].items():
            self.course_schedule.append(course_info(HourMinute.from_str(value['Start Time']),
                                                    HourMinute.from_str(value['End Time']), 
                                                    value['Name'], 
                                                    value['latitude'], 
                                                    value['longitude']))
        self.course_schedule.sort()
        now = HourMinute.utcnow(self.get_local_now())
        found = False
        # 先找「現在」已開始但尚未結束的課
        for i, course in enumerate(self.course_schedule):
            if course.start_time <= now <= course.end_time:
                self.nextCourseIndex = i
                if self.nextCourseIndex == 0:
                    self.currentCourseIndex = len(self.course_schedule) - 1
                else:
                    self.currentCourseIndex = self.nextCourseIndex - 1
                self.cmd_print('SUC', f'Current course in progress: {course.course}')
                self.cmd_print('SUC', 'Courses set up')
                return
        # 如果沒有正在進行的課，則找下一堂課
        if not found:
            self.nextCourseIndex = len(self.course_schedule) - 1
            for i in range(len(self.course_schedule)):
                if now <= self.course_schedule[i].start_time:
                    self.nextCourseIndex = i
                    break
            if self.nextCourseIndex == 0:
                self.currentCourseIndex = len(self.course_schedule) - 1
            else:
                self.currentCourseIndex = self.nextCourseIndex - 1
        self.cmd_print('SUC', 'Courses set up')

    def _send_keys(self, element, string: str):
        for c in string:
            element.send_keys(c)
            self.driver.implicitly_wait(0.5)

    def set_geolocation(self, latitude: float, longitude: float, accuracy: int = 100):
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "accuracy": accuracy
        }
        self.driver.execute_cdp_cmd("Emulation.setGeolocationOverride", params)

    def get_local_now(self):
        tf = TimezoneFinder()
        tz_str = tf.timezone_at(lng=self.longitude, lat=self.latitude)
        tz = pytz.timezone(tz_str)
        return datetime.now(tz)
