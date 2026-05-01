#!/usr/bin/env python3
"""Find matching ChromeDriver URL for installed Chrome version"""
import json
import sys

chrome_version = sys.argv[1]
major_version = chrome_version.split('.')[0]

with open('/tmp/versions.json', 'r') as f:
    data = json.load(f)

# Try exact match first
exact_matches = [
    v for v in data['versions'] 
    if v['version'] == chrome_version 
    and 'chromedriver' in v.get('downloads', {})
]

if exact_matches:
    print(exact_matches[0]['downloads']['chromedriver'][0]['url'])
else:
    # Find latest version with same major version
    matching_major = [
        v for v in data['versions'] 
        if v['version'].startswith(major_version + '.') 
        and 'chromedriver' in v.get('downloads', {})
    ]
    
    if matching_major:
        print(matching_major[-1]['downloads']['chromedriver'][0]['url'])
    else:
        print('')
