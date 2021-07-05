#!/bin/env python

# import libraries
import json
from ratelimit import limits

import requests
from requests_oauthlib import OAuth1Session
from requests_oauthlib import OAuth1

# useful urls
base_url = ''
blocks_url = ''
followers_url = ''
posts_url = ''

# values
client_key = ''
client_secret = '' 
resource_owner_key = ''
resource_owner_secret = ''
queryoauth = ''

def init(tokens, username):
    global base_url, blocks_url, followers_url, posts_url

    base_url = 'http://api.tumblr.com/v2/blog/' + username + '.tumblr.com/'
    blocks_url = base_url + 'blocks'
    followers_url = base_url + 'followers'
    posts_url = base_url + 'posts'

    global client_key, client_secret, resource_owner_key, resource_owner_secret
    client_key = tokens['client_key']
    client_secret = tokens['client_secret']
    resource_owner_key = tokens['resource_owner_key']
    resource_owner_secret = tokens['resource_owner_secret']

    # query signing
    global queryoauth
    queryoauth = OAuth1(client_key, 
        client_secret,
        resource_owner_key, 
        resource_owner_secret,
        signature_type='query')

def add_followers(queryoauth, followers, offset, limit):
    followers_to_add = requests.get(followers_url, params = {"offset": offset, "limit": limit}, auth = queryoauth).json()['response']['users']
    followers.extend(followers_to_add)

# get the subset of the followers list that is mutuals
def get_mutuals(followers):
    return [follower for follower in followers if (follower['following'])]

def add_ask_posts(queryoauth, ask_posts, offset, limit):
    ask_posts_to_add = requests.get(posts_url, params = {"type": type, "tag": tag, "offset": offset, "limit": limit}, auth = queryoauth).json()['response']['users']
    ask_posts.extend(ask_posts_to_add)

def get_ask_posts(queryoauth, max_followers_to_consider):
    type = "answer"
    tag = "spare"
    ask_posts = requests.get(posts_url, params = {"type": type, "tag": tag}, auth = queryoauth).json()['response']['posts']

    range_max = int(max_followers_to_consider // 20)
    last_request_limit = 0

    if range_max * 20 < max_followers_to_consider:
        range_max += 1
        last_request_limit = range_max * 20 - max_followers_to_consider

    for i in range(1, range_max):
        offset = i * 20
        limit = 20

        if i == range_max:
            limit = last_request_limit

        add_ask_posts(queryoauth, ask_posts, offset, limit)

    return ask_posts

# get the subset of the followers list that is mutuals
def get_spared_users(queryoauth, followers, max_followers_to_consider):
    follower_names = [follower['name'] for follower in followers]

    ask_posts = get_ask_posts(queryoauth, max_followers_to_consider)
    return [post for post in ask_posts if post['asking_name'] in follower_names and not post['source_url']]

# after the following function is run, followers should contain a list of dictionaries
# each dictionary item is a follower
# we can only get about 20 followers at a time though
# so to block more people we will need to create additional lists
# using the offset parameter we can make a GET request starting at the 20th follower
# then the 40th, 60th, etc. and then we can append those lists to the first follower list
def get_followers_list(max_followers_to_consider, nice_mode):
    followers = requests.get(followers_url, auth=queryoauth).json()['response']['users']

    range_max = int(max_followers_to_consider // 20)
    last_request_limit = 0

    if range_max * 20 < max_followers_to_consider:
        range_max += 1
        last_request_limit = range_max * 20 - max_followers_to_consider
    
    for i in range(1, range_max):
        offset = i * 20
        limit = 20

        if i == range_max:
            limit = last_request_limit

        add_followers(queryoauth, followers, offset, limit)
    
    mutuals = get_mutuals(followers)
    followers = [follower for follower in followers if follower not in mutuals]
    
    if (nice_mode):
        spared_users = get_spared_users(queryoauth, followers, max_followers_to_consider)
        followers = [follower for follower in followers if follower not in spared_users]
    
    return followers

# define a function that will be used to softblock every follower in non_mutuals		
def softblock(follower):
    block = requests.post(blocks_url, data=follower, auth=queryoauth)
    unblock = requests.delete(blocks_url, data=follower, auth=queryoauth)

    if block.status_code == 201 and unblock.status_code == 200:
        return True
    else:
        return False

# define a function that will be used to softblock every follower in non_mutuals
# tumblr api block and unblock calls are rate limited at 60 requests per minute
# decorator sets limit of 1 call per second, equivalent to 60 calls per minute
# purge() function will iterate through each item in the list, declare a variable containing the parameters needed for the block and unblock calls
# then call softblock() function
@limits(calls=1, period=1)
def purge(tokens, username, max_followers_to_consider, nice_mode):
    init(tokens, username)

    followers = get_followers_list(max_followers_to_consider, nice_mode)

    for follower in followers:
        print("Softblocking " + follower['name'])

        if not softblock(follower):
            print("Something went wrong with softblocking user ", blog)
