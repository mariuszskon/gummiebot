# gummiebot: Gumtree Australia automation software

import requests

import html.parser
import json
import re
import sys, os
import difflib
import getpass

class GummieBot:
    BASE_URL = 'https://www.gumtree.com.au/'

    def __init__(self, username, password):
        self.session = requests.Session()
        self.login(username, password)
        self.ads = {}
        self.category_map = {}

    @property
    def category_map(self):
        CATEGORIES_PAGE = '' # just use the home page
        CATEGORIES_REGEX = re.compile(r'Gtau\.Global\.variables\.categories\s+=\s+({.*?})\s*;')

        if len(self._category_map) <= 0:
            log('Fetching categories...')
            # we need to figure the categories out by getting them from the website
            response = self.session.get(self.BASE_URL + CATEGORIES_PAGE)
            matches = CATEGORIES_REGEX.search(response.text)
            if matches is None:
                raise RuntimeError('Could not extract Gumtree ad categories using known method')
            full_tree = json.loads(matches.group(1))
            GummieCategoryExtractor(full_tree, self._category_map)

        return self._category_map

    @category_map.setter
    def category_map(self, new_map):
        self._category_map = new_map

    def login(self, username, password):
        LOGIN_PAGE = 't-login.html'
        ERROR_STRING = 'notification--error'
        LOGIN_FORM_ID = 'login-form'
        HTML_NAME_USERNAME = 'loginMail'
        HTML_NAME_PASSWORD = 'password'

        log('Getting login form...')
        response = self.session.get(self.BASE_URL + LOGIN_PAGE) # read page once to get nice cookies
        form_parser = GumtreeFormParser(LOGIN_FORM_ID)
        form_parser.feed(response.text)
        inputs = form_parser.close()

        data = {
            HTML_NAME_USERNAME: username,
            HTML_NAME_PASSWORD: password
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

        log('Logging in...')
        response = self.session.post(self.BASE_URL + LOGIN_PAGE, data=data)

        if ERROR_STRING in response.text:
            raise ValueError('Incorrect credentials provided')

        log('Logged in')

    def get_ads(self):
        ADS_PAGE = 'm-my-ads.html'
        log('Getting ads...')
        response = self.session.get(self.BASE_URL + ADS_PAGE)
        ad_parser = GumtreeMyAdsParser()
        ad_parser.feed(response.text)
        self.ads = ad_parser.close()
        return self.ads

    def delete_ad(self, id):
        SUCCESS_STRING = 'notification--success'
        AD_ID_KEY = 'adId'
        DELETE_PAGE = 'm-delete-ad.html'
        DELETE_PAYLOAD_BASE = {
            'show': 'ALL',
            'reason': 'NO_REASON',
            'autoresponse': 0
        }
        data = DELETE_PAYLOAD_BASE
        data[AD_ID_KEY] = str(id)

        log("Deleting ad with id '{}'...".format(id))
        response = self.session.get(self.BASE_URL + DELETE_PAGE, params=data)
        return SUCCESS_STRING in response.text

    def category_name_to_id(self, category_name):
        if category_name in self.category_map:
            return self.category_map[category_name]
        else:
            for name in self.category_map:
                if difflib.SequenceMatcher(None, name, category_name).ratio() > 0.5:
                    raise ValueError("Unknown given category '{}'. Did you mean '{}'?".format(category_name, name))
            raise ValueError("Unknown given category '{}'".format(category_name))

    def post_ad(self, ad: 'GumtreeListing'):
        SUCCESS_STRING = 'notification--success'
        DELETE_DRAFT_PAGE = 'p-post-ad.html'
        FORM_PAGE = 'p-post-ad2.html'
        FORM_ID = 'pstad-main-form'
        UPLOAD_IMAGE_TARGET = 'p-upload-image.html'
        DESIRED_IMAGE_URL_KEY = 'teaserUrl'
        DRAFT_TARGET = 'p-post-draft-ad.html'
        SUBMIT_TARGET = 'p-submit-ad.html'

        # delete any existing drafts
        log('Deleting drafts...')
        self.session.get(self.BASE_URL + DELETE_DRAFT_PAGE, params={'delDraft': 'true'})

        # we need to pass the first page of the form and go to the main one
        data_to_get_form = {
            'title': ad.title,
            'categoryId': self.category_name_to_id(ad.category),
            'adType': 'OFFER',
            'shouldShowSimplifiedSyi': 'false'
        }

        log('Getting ad post form...')
        response = self.session.post(self.BASE_URL + FORM_PAGE, data=data_to_get_form)
        form_parser = GumtreeFormParser(FORM_ID)
        form_parser.feed(response.text)
        inputs = form_parser.close()

        condition_field_name = False

        submission = {
            # we do need need to set category and title because we already provided it to the form page
            'description': ad.description,
            'price.amount': ad.price['amount'],
            'price.type': ad.price['type']
        }
        for input_tag in inputs:
            if 'name' not in input_tag:
                continue
            if input_tag['name'] in submission:
                # do not override our values
                pass
            else:
                if input_tag.get('type') == 'checkbox':
                    pass
                else:
                    submission[input_tag['name']] = input_tag.get('value', '')
                    if 'condition' in input_tag['name']:
                        condition_field_name = input_tag['name']
        if condition_field_name == False:
            raise RuntimeError('Could not extract field name for item condition using known method')
        submission[condition_field_name] = ad.condition

        image_links = []
        log('Uploading images...')
        for image in ad.images:
            log("Uploading image '{}'...".format(image))
            response = self.session.post(self.BASE_URL + UPLOAD_IMAGE_TARGET, data=submission, files={
                'images': open(image, 'rb')
            })
            try:
                url = response.json()[DESIRED_IMAGE_URL_KEY]
                image_links.append(url)
            except:
                raise RuntimeError("Could not extract uploaded image URL for image '{}'".format(image))
        submission['images'] = image_links

        # post a draft in case the actual submission fails (to make it easier for human to post)
        log('Posting draft...')
        draft_response = self.session.post(self.BASE_URL + DRAFT_TARGET, data=submission)

        log('Posting final listing...')
        response = self.session.post(self.BASE_URL + SUBMIT_TARGET, data=submission)

        return SUCCESS_STRING in response.text

class GumtreeFormParser(html.parser.HTMLParser):
    def __init__(self, target_id):
        super().__init__()
        self.inputs = []
        self.inside_desired_form = False
        self.target_id = target_id

    def handle_starttag(self, tag, attrs):
        if tag == 'form':
            for attr in attrs:
                if attr[0] == 'id' and self.target_id in attr[1]:
                    self.inside_desired_form = True
                    break
        if self.inside_desired_form and tag == 'input':
            attrdict = {}
            # convert tuples like ('id', 'login-password') to dictionary where attrdict['id'] = 'login-password'
            for attr in attrs:
                attrdict[attr[0]] = attr[1]
            self.inputs.append(attrdict)


    def handle_endtag(self, tag):
        if tag == 'form':
            self.inside_desired_form = False

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

class GumtreeListing():
    KNOWN_PRICE_TYPES = ['FIXED', 'NEGOTIABLE', 'GIVE_AWAY', 'SWAP_TRADE']
    KNOWN_CONDITIONS = ['used', 'new']

    def __init__(self, title, description, price, category, condition, images):
        self.title = title
        self.description = description

        if not isinstance(price, dict):
            raise TypeError("Expected 'price' element to be an object/dictionary")
        if 'amount' not in price or 'type' not in price:
            raise ValueError("Expected subkeys 'amount' and 'type' in 'price'")
        self.price = {}
        try:
            self.price['amount'] = float(price['amount'])
        except ValueError:
            raise ValueError("'amount' is not a valid decimal number")
        if self.price['amount'] <= 0:
            raise ValueError("'amount' must be greater than zero")
        if price['type'] not in self.KNOWN_PRICE_TYPES:
            raise ValueError("Price type '{}' unknown".format(price['type']))
        self.price['type'] = price['type']

        self.category = category
        if condition not in self.KNOWN_CONDITIONS:
            raise ValueError("Condition '{}' unknown".format(condition))
        self.condition = condition
        self.images = images

    def debug(self):
        return {
            'title': self.title,
            'description': self.description,
            'price': self.price,
            'category': self.category,
            'condition': self.condition,
            'images': self.images
        }

def GummieJsonParser(directory):
    GUMMIE_JSON_FILENAME = 'meta.gummie.json'
    DEFAULT_CONDITION = 'used'

    log("Switching to directory '{}'...".format(directory))
    os.chdir(directory)

    log("Opening '{}'...".format(GUMMIE_JSON_FILENAME))
    with open(GUMMIE_JSON_FILENAME) as f:
        log("Parsing '{}'...".format(GUMMIE_JSON_FILENAME))
        raw_data = json.load(f)
        listing_data = {}
        listing_data['title'] = raw_data['title']
        with open(os.path.join(directory, raw_data['description_file'])) as f2:
            listing_data['description'] = f2.read()
        listing_data['price'] = raw_data['price']
        listing_data['category'] = raw_data['category']
        listing_data['condition'] = raw_data.get('condition', DEFAULT_CONDITION)
        listing_data['images'] = []
        for image in raw_data['images']:
            if not os.path.isfile(image):
                raise FileNotFoundError("Could not find image '{}'".format(image))
            listing_data['images'].append(image)
        return GumtreeListing(**listing_data)

def GummieCategoryExtractor(tree, category_map):
    # extract only the "leaf" categories (categories with no children)
    # because only they can be normally selected

    if len(tree["children"]) > 0:
        for child in tree["children"]:
            GummieCategoryExtractor(child, category_map)
    else:
        category_map[tree["name"]] = tree["id"]

def log(message, end='\n'):
    sys.stderr.write(str(message) + str(end))

if len(sys.argv) < 2:
    log('Please enter one or more directories to scan as arguments on the command line')
    sys.exit()

listing = GummieJsonParser(sys.argv[1])
log(str(listing.debug()))

log('Username: ', end='')
username = input('')
password = getpass.getpass('Password: ', sys.stderr)

gb = GummieBot(username, password)

log(json.dumps(gb.category_map, sort_keys=True, indent=4))

log(gb.get_ads())

log(gb.post_ad(listing))
