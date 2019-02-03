# gummiebot: Gumtree Australia automation software

import urllib.request, urllib.parse, http.cookiejar
import html.parser

class GummieBot:
    BASE_URL = 'https://www.gumtree.com.au/'
    HTML_NAME_USERNAME = 'loginMail'
    HTML_NAME_PASSWORD = 'password'

    def __init__(self, username, password):
        cookiejar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookiejar))
        self.login(username, password)

    def login(self, username, password):
        LOGIN_PAGE = 't-login.html'

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
                    raise ValueError("Unexpected input tag with name '{}'".format(input_tag['name']))

        response = self.opener.open(self.BASE_URL + LOGIN_PAGE,
                                    urllib.parse.urlencode(data).encode('utf-8')
        )

    def get_ads(self):
        ADS_PAGE = 'm-my-ads.html'
        response = self.opener.open(self.BASE_URL + ADS_PAGE)
        print(response.read().decode('utf-8'))

class GumtreeLoginFormParser(html.parser.HTMLParser):
    LOGIN_FORM_ID = 'login-form'

    def __init__(self):
        super().__init__()
        self.inputs = []
        self.inside_login_form = False

    def handle_starttag(self, tag, attrs):
        if tag == 'form':
            for attr in attrs:
                if attr[0] == 'id' and attr[1] == self.LOGIN_FORM_ID:
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

gb = GummieBot("user", "pass")
gb.get_ads()
