import zipfile, io
import re
import requests
from requests.exceptions import ConnectionError
import urllib.parse as urlparse

import os
import sys
import threading

from bs4 import BeautifulSoup




class PingPong_session(requests.Session):
    def __init__(self, username, password):
        headers = { 'user-agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36' }
        super().__init__()
        self.headers.update(headers)
        self.login(username, password)
        
        # Test fetching lecture notes from image analysis
        # TODO: Make this into function which downloads a file and displays a progress bar
        #os.mkdir('img')
        #r = self.get('https://pingpong.chalmers.se/zipNode.do?node=5139402', stream=True)
        #print('Downloading files')
        #z = zipfile.ZipFile(io.BytesIO(r.content))
        #z.extractall('img/') 
        #print('Download finished')

        self.courses = self.get_all_course_ids()

        for course_id, course_name in self.courses.items():
            # Create folder for course
            course_name = re.sub('[\\/:*?"<>|]', '', course_name)
            os.mkdir(course_name)
            extract_path = course_name + '/'
            
            # TODO: Check if this is none
            file_ids = self.get_file_ids(course_id)

            # Download files for course
            print('Starting download for course ', course_name)
            self.download_files(file_ids, extract_path)
        
        # IDEA:
        # get_all_course_ids to get course ids and names
        # create folder for course name, use this as extract_path
        # for each course, do get_file_ids
        # for each id in get_file_ids, do download_files

    def get_all_course_ids(self):
        # Get a dict of all courses and their ids
        url = 'https://pingpong.chalmers.se/listCourses.do?tablePageSizemyCourses=100'
        r = self.get(url)

        # For parsing the course ids of the page
        soup = BeautifulSoup(r.content, 'html.parser')
        courses = dict()

        # Get table of courses
        courses_html = soup.find('table', {'id': 'myCourses'}).find('tbody').find_all('tr')

        for course in courses_html:
            course_id = course.get('id', None).split('_')[2]
            course_name = course.find('td', {'data-column': 'Aktivitet: '}).find('span', {'class': 'dynamic-data'}).text

            courses[course_id] = course_name

        return courses
        
    def get_file_ids(self, course_id):
    # Takes an id of a course and returns the ids of all of the files in the courseDocsAndFiles directory
        r = self.get('https://pingpong.chalmers.se/courseId/' + str(course_id) + '/courseDocsAndFiles.do')

        # Soup for parsing ids
        soup = BeautifulSoup(r.content, 'html.parser')
        file_ids = list()

        # If course does not have any documents, return
        try:
            documents = soup.find('div', {'id': 'courseLib'}).find('div', {'class': 'box-body clearfix'}).find_all('div', {'class': 'treeNodeSuffix'})
        except AttributeError:
            return

        for document in documents:
            file_ids.append(document.find('input', {'type': 'checkbox'}).get('value', None))

        return file_ids

    def download_file(self, file_id, extract_path):
        # Download a file and save as zip, then extract the zip into extract_path folder
        print('started download of ', file_id)
        r = self.get('https://pingpong.chalmers.se/zipNode.do?node=' + str(file_id), stream=True)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(extract_path)
        # TODO: display progress bar

    def download_files(self, file_ids, extract_path):
        # Calls download_file for all files in a course in separate threads

        # Create threads
        threads = [threading.Thread(target=self.download_file, args=(id, extract_path,)) for id in file_ids]
        print('starting ', len(threads), ' downloads')
        # Start threads
        [t.start() for t in threads]
        # Wait for threads to join
        [t.join() for t in threads]

    def login(self, username, password):
        # Logs user in and retrieves all nessecary cookies etc.

        # Retrieve SAML token by being redirected
        r = self.get('https://pingpong.chalmers.se/')

        parsed = urlparse.urlparse(r.url)
        RelayState = urlparse.parse_qs(parsed.query)['RelayState'][0]
        SAMLRequest = urlparse.parse_qs(parsed.query)['SAMLRequest'][0]

        # Parse into bs4 to get some important context from site
        soup = BeautifulSoup(r.content, 'html.parser')
        data = dict()

        # Parse hidden context from site
        for hidden in soup.find_all('input', type='hidden'):
            data[hidden['name']] = hidden['value']

        # User for data goes here
        data['ctl00$ContentPlaceHolder1$UsernameTextBox'] = username
        data['ctl00$ContentPlaceHolder1$PasswordTextBox'] = password
        data['ctl00$ContentPlaceHolder1$SubmitButton'] = 'Logga in'
        
        login_url = 'https://idp.chalmers.se/adfs/ls/'

        # Login
        r = self.post(login_url, data=data, params = { 'SAMLRequest': SAMLRequest, 'RelayState': RelayState })

        # Retrieve SAMLResponse
        r = self.get(r.url)
        soup = BeautifulSoup(r.content, 'html.parser')

        SAMLResponse = soup.find('input', type='hidden')['value']

        # Validate SAMLResponse
        url = 'https://pingpong.chalmers.se/Shibboleth.sso/SAML2/POST'
        r = self.post(url, data={ 'SAMLResponse': SAMLResponse, 'RelayState': RelayState })

        # We are now logged in!


if __name__ == '__main__':
    user = input('Username:\n')
    import getpass
    password = getpass.getpass()
    p = PingPong_session(user, password)
