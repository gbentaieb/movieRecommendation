import os
import sys
import csv
import requests
import time
from random import randint

GENRES = ['Action Film', 'Adventure Film', 'Animation', 'Comedy', 'Drama',
          'Family', 'Fantasy', 'Mystery', 'Romance Film', 'Science Fiction', 
          'Thriller']

if __name__ == "__main__":
    module_dir = os.path.dirname(sys.argv[0])
else:
    module_dir = os.path.dirname(__file__)
delimiter = ';'

read_file = os.path.join(module_dir, 'db_data.csv')
write_file = os.path.join(module_dir, 'imdb_id.csv')

with open(read_file, 'r') as rf:
    with open(write_file, 'w') as wf:
        reader = csv.DictReader(rf, delimiter=delimiter)
        writer = csv.writer(wf, delimiter=delimiter, lineterminator = '\n')
        for row in reader:
            mid = row['mid']
            if not mid:
                continue
            fb_query = 'https://www.googleapis.com/freebase/v1/mqlread?query='
            fb_query += """[{{
                              "type": "/film/film",
                              "mid": "{mid}",
                              "imdb_id": []
                              }}]""".format(mid=mid)
            fb_query += '&key=' + 'AIzaSyAyq30J2ioPQhkRzj0G8si2Se7jQA8qmPE'
            received = False
            while(not received):
                try:
                    fb_request = requests.get(fb_query).json()
                    if fb_request.get('error'):
                        if fb_request['error'].get('code') == 403:
                            print('User Rate Limit Exceeded')
                            time.sleep(1)
                            continue
                        else:
                            print(fb_request)
                    else:
                        result = fb_request['result']
                except Exception as e:
                    print(e)
                received = True
            try:
                imdb_id = result[0]['imdb_id'][0]
            except:
                imdb_id = None
            writer.writerows([[imdb_id]])