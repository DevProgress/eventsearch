""" Deletes any events older than this moment in time. Should be run daily, probably early in the morning (say 3am) to flush out
events from the previous day.
"""


__author__ = 'Jay Johnston'



import boto3
import datetime
import json

cloudsearchdomain = boto3.client('cloudsearchdomain',
                                 endpoint_url="http://doc-hillaryevents-toacvf6ghscgs4hixl2mzyoihq.us-east-1.cloudsearch.amazonaws.com")

now = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
old_events = cloudsearchdomain.search(queryParser='structured',query="date:{,'" + now + "']",returnFields='_no_fields',size=10000)

if(old_events['hits']['found'] < 1):
    print "No old events found"
    exit()

# get event by id:
# id = u'4109549'
# testevent = cloudsearchdomain.search(queryOptions="{'fields':['_id']}", query=id)
cloudsearch_delete_batch = []

for event_id in old_events['hits']['hit']:
    payload = {}
    payload['type'] = "delete"
    payload['id'] = str(event_id['id'])

    cloudsearch_delete_batch.append(payload)

#print json.dumps(cloudsearch_delete_batch)
response = cloudsearchdomain.upload_documents(documents=json.dumps(cloudsearch_delete_batch), contentType='application/json')
print response