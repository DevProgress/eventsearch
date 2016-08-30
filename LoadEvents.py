"""
Loads current and future events from the hillaryclinton.com event API into a CloudSearch instance that is set to search on the following fields:

Address, city, date, description, location (as lat/lon), name, state, and zipcode.

Each of the above fields contains the content from the original JSON event and the entire original payload is lz4 compressed and base64 encoded
into the 'content' field.

A sample query:
curl "http://search-hillaryevents-toacvf6ghscgs4hixl2mzyoihq.us-east-1.cloudsearch.amazonaws.com/2013-01-01/search?q='Voter+Registration+Dillwyn+Virginia'”

Submissions to CloudSearch are batched into payloads of roughly 5M, as the docs say that is the optimal size.

This script is intended to be run several times a day to pick up new events and event changes. Cloudsearch will return the newest version
of the data.
"""

__author__ = 'Jay Johnston'
import requests
import json
import lz4
import base64
import sys
import boto3
import re
import commands
import dateutil.parser

output_file = False # set this to True to have this program generate a /tmp/hillevents.json file that can be uploaded to AWS for index analysis

end = False
url = "https://www.hillaryclinton.com/api/events/events?perPage=100&status=confirmed&visibility=public&page={page}"
page_num = 1
cloudsearch = client = boto3.client('cloudsearch',
                                    endpoint_url="http://doc-hillaryevents-toacvf6ghscgs4hixl2mzyoihq.us-east-1.cloudsearch.amazonaws.com")
cloudsearchdomain = boto3.client('cloudsearchdomain',
                           endpoint_url="http://doc-hillaryevents-toacvf6ghscgs4hixl2mzyoihq.us-east-1.cloudsearch.amazonaws.com")

cloudsearch_payload = []
cloudsearch_payload_count = 0

RE_XML_ILLEGAL = u'([\u0000-\u0008\u000b-\u000c\u000e-\u001f\ufffe-\uffff])' + \
                 u'|' + \
                 u'([%s-%s][^%s-%s])|([^%s-%s][%s-%s])|([%s-%s]$)|(^[%s-%s])' % \
                 (unichr(0xd800),unichr(0xdbff),unichr(0xdc00),unichr(0xdfff),
                  unichr(0xd800),unichr(0xdbff),unichr(0xdc00),unichr(0xdfff),
                  unichr(0xd800),unichr(0xdbff),unichr(0xdc00),unichr(0xdfff))

rm_invalid_chars = re.compile(RE_XML_ILLEGAL)

def clean(string):
    return rm_invalid_chars.sub("?", string)

max_attempts = 10

while(not end):

    attempts = 0
    giveup = False
    have_response = False

    while(not giveup and not have_response):
        try:
            response = requests.get(url.format(page=page_num))
            have_response = True
        except requests.exceptions.ConnectionError, e:
            attempts += 1
            if(attempts < max_attempts):
                print "Unable to get event page. Trying again."
                continue
            else:
                giveup = True
                print "Unable to get any events after trying 10 times. Quitting."
                exit()

    if(response.status_code == 200):
        print url.format(page=page_num)
        responseJson = response.json()
        total_pages = responseJson['meta']['totalPages']

        print total_pages
        if(page_num >= total_pages):
            end = True

        events = responseJson['events']

        for event in events:
            startTime = None
            endTime = None
            if(event['endDate']):
                endTime = dateutil.parser.parse(event['endDate'])
            if(event['startDate']):
                startTime = dateutil.parser.parse(event['startDate'])

            time = None
            if(endTime):
                time = endTime
            elif(startTime):
                time = startTime

            if(time):
                now = dateutil.parser.parse(commands.getoutput("date"))

                if(time < now):
                    continue

            payload = {}
            payload['type'] = "add"
            payload['id'] = str(event['id'])
            fields = payload['fields'] = {}
            fields['name'] = clean(event['name'])
            try:
                fields['description'] = clean(event['description'])
            except UnicodeEncodeError, e:
                try:
                    print event['description']
                except IndexError:
                    print "Error decoding description"
                    continue

            if(event['locations']):
                location = event['locations'][0]

                if(location['latitude'] and location['longitude']):
                    fields['location'] = location['latitude'] + "," + location['longitude']
                fields['zipcode'] = location['postalCode']
                fields['address'] = location['address1']
                fields['city'] = location['city']
                fields['state'] = location['state']
            fields['date'] = event['startDate']

            fields['content'] = base64.b64encode(lz4.dumps(json.dumps(event)))

            #print "sizeof content compressed:" + str(sys.getsizeof(fields['content']))

            content_size = sys.getsizeof(fields['content'])
            if(content_size > 4096):
                print "Huge payload skipped: " + str(content_size)
            else:
                cloudsearch_payload.append(payload)
                cloudsearch_payload_count += 1

        print "cloudsearch payload count: " + str(cloudsearch_payload_count)

        if(cloudsearch_payload_count >= 1800 or end is True): # cloudsearch likes a <5M payload. Each payload is ~2500K.
            print "Sending to Cloudsearch"
            response = cloudsearchdomain.upload_documents(documents=json.dumps(cloudsearch_payload), contentType='application/json')
            print response
            cloudsearch_payload = []
            cloudsearch_payload_count = 0

        if(output_file):
            if(page_num == 3):
                with open('/tmp/hillevents.json', 'w+') as f:
                    f.write(json.dumps(cloudsearch_payload))
                print "/tmp/hillevents.json has been written"
                exit()

        page_num += 1

    else:
        end = True

