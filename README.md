# gummiebot: Gumtree Australia automation software

Get your ads, post new ads, and delete them automatically.

## Installation

    git clone https://github.com/mariuszskon/gummiebot
    cd gummiebot
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt

## Command line usage

    usage: gummiebot COMMAND DIRECTORY...
           COMMAND is one of post, delete or repost

More than one directory can be provided. These will be processed one-by-one in order, but will only require logging in once.

Your directory must have a `meta.gummie.json` file describing the ad.

## meta.gummie.json

### Example

    {
        "title": "HDMI cables",
        "price": {
            "amount": 4,
            "type": "FIXED"
        },
        "condition": "new",
        "description_file": "desc",
        "category": "TV Accessories",
        "images": [
            "img01.jpg",
            "img02.jpg"
        ]
    }

### Required properties

#### `title`

The name of the ad, as a string.

#### `description_file`

A string which provides the filename of a pure text file relative to the directory of `meta.gummie.json`. This is used as the description on the Gumtree ad.

#### `price`

An object containing the properties `amount` and `type`.

##### `amount`

The asking price, in Australian dollars, provided via a type which can be converted to a float (decimal) easily. Must be greater than zero.

##### `type`

A string, one of `FIXED`, `NEGOTIABLE`, `GIVE_AWAY` or `SWAP_TRADE`, corresponding to the type of price on Gumtree.

#### `category`

A string which exactly matches one of the final categories on Gumtree. That is, this is a category which you can post under, not a broad category.

Yes: `Fiction Books`

No: `Books`

#### `images`

An array of strings, each providing the filename of an image relative to the directory of `meta.gummie.json`. Each image is uploaded to support the ad, in the order provided.

### Optional properties

#### `condition`

A string, one of `used` or `new`. Defaults to `used`.

## API usage

Undocumented functions/methods/classes are intended for internal use only.

### `gummie_json_parse(directory: str) -> GumtreeListing`

Changes to directory `directory` and reads the `meta.gummie.json` file inside. Returns an instance of `GumtreeListing` which contains validated data that can be used later with `GummieBot`.

### `GummieBot(username, password)`

Big class for interacting with Gumtree Australia, but not without logging in first.

#### `.category_map`

A dict of "leaf" categories (ones which ads can be submitted to), with mappings to their corresponding IDs. This is lazy loaded from the website.

#### `.category_name_to_id(category_name)`

Provides a higher-level interface to reading a value using a key from `category_map` by logging if the key could not be found, and suggesting similar keys.

#### `.get_ads()`

Returns a dict of the logged in user's ads, with a mapping from the title to the ad's ID.

#### `.delete_ad(id) -> bool`

Delete an ad by its ID. The ad ID can be acquired by first using `.get_ads()`. Returns boolean indicating success or failure.

#### `.post_ad(ad: GumtreeListing) -> bool`

Posts an instance of `GumtreeListing` to Gumtree. Returns boolean indicating success or failure.
