# gummiebot: Gumtree Australia automation software

import urllib.request, urllib.parse, http.cookiejar
import html.parser
import re
import sys
import getpass

class GummieBot:
    BASE_URL = 'https://www.gumtree.com.au/'
    HTML_NAME_USERNAME = 'loginMail'
    HTML_NAME_PASSWORD = 'password'

    def __init__(self, username, password):
        cookiejar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookiejar))
        self.login(username, password)
        self.ads = {}

    def login(self, username, password):
        LOGIN_PAGE = 't-login.html'
        ERROR_STRING = 'notification--error'

        response = self.opener.open(self.BASE_URL + LOGIN_PAGE) # read page once to get nice cookies
        form_parser = GumtreeLoginFormParser()
        form_parser.feed(response.read().decode('utf-8'))
        inputs = form_parser.close()

        data = {
            self.HTML_NAME_USERNAME: username,
            self.HTML_NAME_PASSWORD: password
        }
        for input_tag in inputs:
            if input_tag['name'] in data:
                # we already have data to handle this (e.g. username + password)
                pass
            else:
                # blindly copy hidden inputs (e.g. CSRF token)
                if input_tag['type'] == 'hidden':
                    data[input_tag['name']] = input_tag['value']
                elif input_tag['type'] == 'checkbox':
                    data[input_tag['name']] = 'true' # check the box
                else:
                    raise ValueError("Unexpected input tag type '{}' (with name '{}')".format(input_tag['type'], input_tag['name']))

        response = self.opener.open(self.BASE_URL + LOGIN_PAGE,
                                    urllib.parse.urlencode(data).encode('utf-8')
        )

        if ERROR_STRING in response.read().decode('utf-8'):
            raise ValueError('Incorrect credentials provided')

    def get_ads(self):
        ADS_PAGE = 'm-my-ads.html'
        response = self.opener.open(self.BASE_URL + ADS_PAGE)
        ad_parser = GumtreeMyAdsParser()
        ad_parser.feed(response.read().decode('utf-8'))
        self.ads = ad_parser.close()
        print(self.ads)

    def delete_ad(self, id):
        AD_ID_KEY = 'adId'
        DELETE_PAGE = 'm-delete-ad.html?' # ? for GET request
        DELETE_PAYLOAD_BASE = {
            'show': 'ALL',
            'reason': 'NO_REASON',
            'autoresponse': 0
        }
        data = DELETE_PAYLOAD_BASE
        data[AD_ID_KEY] = str(id)

        self.opener.open(self.BASE_URL + DELETE_PAGE + # MUST use + to send GET data instead of POST
                         urllib.parse.urlencode(data)
        )


class GumtreeLoginFormParser(html.parser.HTMLParser):
    LOGIN_FORM_ID = 'login-form'

    def __init__(self):
        super().__init__()
        self.inputs = []
        self.inside_login_form = False

    def handle_starttag(self, tag, attrs):
        if tag == 'form':
            for attr in attrs:
                if attr[0] == 'id' and self.LOGIN_FORM_ID in attr[1]:
                    self.inside_login_form = True
                    break
        if self.inside_login_form and tag == 'input':
            attrdict = {}
            # convert tuples like ('id', 'login-password') to dictionary where attrdict['id'] = 'login-password'
            for attr in attrs:
                attrdict[attr[0]] = attr[1]
            self.inputs.append(attrdict)


    def handle_endtag(self, tag):
        if tag == 'form':
            self.inside_login_form = False

    def close(self):
        return self.inputs

class GumtreeMyAdsParser(html.parser.HTMLParser):
    DESIRED_TAG_ELEMENT = 'a'
    DESIRED_TAG_CLASS = 'rs-ad-title'
    AD_ID_REGEX = re.compile('adId=(\d+)')

    def __init__(self):
        super().__init__()
        self.ads = {}
        self.desired_tag = False
        self.last_ad_id = -1

    def handle_starttag(self, tag, attrs):
        self.desired_tag = False
        if tag == self.DESIRED_TAG_ELEMENT:
            for attr in attrs:
                if attr[0] == 'class' and self.DESIRED_TAG_CLASS in attr[1]:
                    self.desired_tag = True

        if self.desired_tag:
            for attr in attrs:
                if attr[0] == 'href':
                    self.last_ad_id = self.AD_ID_REGEX.search(attr[1]).group(1)
                    self.ads[self.last_ad_id] = ''

    def handle_data(self, data):
        # if we are inside a tag with the ad title, get the title
        if self.desired_tag:
            self.ads[self.last_ad_id] += data

    def handle_endtag(self, tag):
        if self.desired_tag:
            # assume same type of tag is not nested
            if tag == self.DESIRED_TAG_ELEMENT:
                self.desired_tag = False

    def close(self):
        return self.ads

sys.stderr.write('Username: ')
username = input('')
password = getpass.getpass('Password: ', sys.stderr)

gb = GummieBot(username, password)
gb.get_ads()
