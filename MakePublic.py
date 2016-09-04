__author__ = 'jay'

from multiprocessing.dummy import Pool as ThreadPool
import boto3
s3 = boto3.resource('s3')
pool = ThreadPool(8)

def make_public(obj):
    obj.Acl().put(ACL='public-read')
    print(obj.key)


results = pool.map(make_public, s3.Bucket('hillaryevents').objects.all())

