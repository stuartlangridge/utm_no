"Handle all the URL stripping"

import re
import urllib.parse
import unittest
import requests
import logging
import os

LOGLEVEL = os.environ.get('LOGLEVEL', 'WARNING').upper()
logging.basicConfig(level=LOGLEVEL)

# from https://github.com/rknightuk/TrackerZapper/blob/main/TrackerZapper/AppDelegate.swift#L160
STRIP_URL_QUERY_ELEMENTS_STARTS = [
    "_bta_c", "_bta_tid", "_ga", "_hsenc", "_hsmi", "_ke", "_openstat",
    "dm_i", "ef_id", "epik", "fbclid", "gclid", "gclsrc", "gdffi", "gdfms",
    "gdftrk", "hsa_", "igshid", "matomo_", "mc_", "mkwid", "msclkid", "mtm_",
    "ns_", "oly_anon_id", "oly_enc_id", "otc", "pcrid", "piwik_", "pk_",
    "rb_clickid", "redirect_log_mongo_id", "redirect_mongo_id", "ref",
    "s_kwcid", "sb_referer_host", "soc_src", "soc_trk", "spm", "sr_",
    "srcid", "stm_", "trk_", "twclid", "utm_", "vero_", "utm-"
]

# https://stackoverflow.com/a/44645567/1418014
URL_REGEX = re.compile(r"""
    (
        (?:
            (?:https|http)?
            :
            (?:
                /{1,3}
                |
                [a-z0-9%]
            )
            |
            [a-z0-9.\-]+[.](?:com|org|uk)
        /)
        (?:
            [^\s()<>{}\[\]]+
            |
            \([^\s()]*?\([^\s()]+\)[^\s()]*?\)
            |
            \([^\s]+?\)
        )+
        (?:
            \([^\s()]*?\([^\s()]+\)[^\s()]*?\)
            |
            \([^\s]+?\)
            |
            [^\s`!()\[\]{};:'".,<>?«»“”‘’]
        )
        |
        (?:
            (?<!@)[a-z0-9]+
            (?:
                [.\-][a-z0-9]+
            )*
            [.](?:com|uk|ac)\b/?
            (?!@)
        )
    )
""", re.VERBOSE)

REDIRECT_CACHE = {}


def follow_redirects(url):
    if url in REDIRECT_CACHE:
        logging.debug(f"URL {url} -> {REDIRECT_CACHE[url]} (cached)")
        return REDIRECT_CACHE[url]
    response = requests.get(url)
    REDIRECT_CACHE[url] = response.url
    logging.debug(f"URL {url} -> {REDIRECT_CACHE[url]}")
    return response.url


def fix_url(url, handle_tco=False):
    """Removes all querystring params with a prohibited prefix.
    Call this with actual URLs only.
    Must return text unchanged if there is no replacing to be done."""
    parsed = urllib.parse.urlsplit(url)
    qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    qs_keys = qs.keys()
    ok_qs_keys = [
        k for k in qs_keys
        if not any([k.startswith(b) for b in STRIP_URL_QUERY_ELEMENTS_STARTS])
    ]
    if len(ok_qs_keys) == len(qs_keys):
        endurl = url  # if removed nothing, change nothing
    else:
        nqs = dict([(k, qs[k]) for k in ok_qs_keys])
        parsed = parsed._replace(query=urllib.parse.urlencode(nqs, doseq=True))
        endurl = urllib.parse.urlunsplit(parsed)
    if handle_tco and parsed.netloc == "t.co":
        logging.debug(f"Looking up t.co URL {endurl} to get ultimate endpoint")
        endurl = follow_redirects(endurl)
    return endurl


def fix_match_object(mo, handle_tco=False):
    return fix_url(mo.group(0), handle_tco)


def fix_text(text, handle_tco=False):
    """Fixes all URLs within text.
    If handle_tco is True, will also blockingly(!) resolve t.co links
    """
    return URL_REGEX.sub(lambda mo: fix_match_object(mo, handle_tco), text)


def is_url(s):
    "Only true if the passed s is exactly a URL and nothing else, no whitespace"
    if type(s) is not str:
        return False
    return bool(URL_REGEX.match(s))


def contains_tco(text):
    urls_in_text = URL_REGEX.findall(text)
    return any([urllib.parse.urlparse(u).netloc == "t.co" for u in urls_in_text])


class TestIsUrl(unittest.TestCase):
    def test_nope(self):
        self.assertFalse(is_url(None))
        self.assertFalse(is_url("lol"))
        self.assertFalse(is_url(9))
        self.assertFalse(is_url("http"))
        self.assertFalse(is_url("pants://example.com"))
        self.assertFalse(is_url("hppp://example.com"))

    def test_yep(self):
        self.assertTrue(is_url("http://example.com"))
        self.assertTrue(is_url("https://example.com"))
        self.assertTrue(is_url("https://example.com?lol=1"))
        self.assertTrue(is_url("https://kryogenix.org/days"))
        self.assertTrue(is_url("http://example.com/a/b?utm_source=haha"))
        self.assertTrue(is_url("https://google.com"))
        self.assertTrue(is_url("https://nope.museum?param=123#frag1"))
        self.assertTrue(is_url("https://nope.museum:8000?param=123#frag1"))
        self.assertTrue(is_url("https://a:b@nope.museum:8000?param=123#frag1"))

class TestFixUrl(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(fix_url("lol"), "lol")
        self.assertEqual(fix_url(None), None)

    def test_unchanged(self):
        self.assertEqual(fix_url("https://kryogenix.org/"),
                         "https://kryogenix.org/")
        self.assertEqual(fix_url("http://kryogenix.org/"),
                         "http://kryogenix.org/")
        self.assertEqual(fix_url("https://kryogenix.org/?untouched"),
                         "https://kryogenix.org/?untouched")
        self.assertEqual(fix_url("https://kryogenix.org/?untouched=ok"),
                         "https://kryogenix.org/?untouched=ok")
        self.assertEqual(fix_url("https://kryogenix.org/?a=1&b=2"),
                         "https://kryogenix.org/?a=1&b=2")

    def test_changed(self):
        self.assertEqual(fix_url("https://kryogenix.org/?utm_source=bye"),
                         "https://kryogenix.org/")
        self.assertEqual(fix_url("https://kryogenix.org/?utm_source=bye&a=1"),
                         "https://kryogenix.org/?a=1")
        self.assertEqual(fix_url("https://kryogenix.org/?utm_source=bye&utm_media=banner"),
                         "https://kryogenix.org/")
        self.assertEqual(fix_url("https://kryogenix.org/?srcid=12345"),
                         "https://kryogenix.org/")
        # TrackerZapper's amusing test :-)
        self.assertEqual(fix_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&s=never&fbclid=gunna&gclid=give&gclsrc=you&utm_content=up&utm_term=never&utm_campaign=gunna&utm_medium=let&utm_source=you&utm_id=down&_ga=never&mc_cid=gunna&mc_eid=run&_bta_tid=around&_bta_c=and&trk_contact=desert&trk_msg=you&trk_module=never&trk_sid=gunna&gdfms=make&gdftrk=you&gdffi=cry&_ke=never&redirect_log_mongo_id=gunna&redirect_mongo_id=say&sb_referer_host=goodbye&mkwid=never&pcrid=gunna&ef_id=tell&s_kwcid=a&msclkid=lie&dm_i=and&epik=hurt&pk_campaign=you"),
                         "https://www.youtube.com/watch?v=dQw4w9WgXcQ&s=never")

    def test_tricks(self):
        self.assertEqual(fix_url("https://kryogenix.org/utm_source=bye/?a=1"),
                         "https://kryogenix.org/utm_source=bye/?a=1")


class TestExtractUrl(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(URL_REGEX.findall("https://kryogenix.org"),
                         ["https://kryogenix.org"])
        self.assertEqual(URL_REGEX.findall("Testing https://kryogenix.org for urls"),
                         ["https://kryogenix.org"])

    def test_complex_urls(self):
        self.assertEqual(URL_REGEX.findall("""
        This is https://a:b@kryogenix.org:80/lol?a=b#frag1 here
        """),
                         ["https://a:b@kryogenix.org:80/lol?a=b#frag1"])

    def test_multiple_urls(self):
        self.assertEqual(URL_REGEX.findall("""
        You can go to https://kryogenix.org/days or
        http://example.com/a/b?utm_source=haha
        or https://google.com or https://nope.museum?param=123#frag1 or
        any other place you fancy
        """),
                         [
                         "https://kryogenix.org/days",
                         "http://example.com/a/b?utm_source=haha",
                         "https://google.com",
                         "https://nope.museum?param=123#frag1"
                         ])

class TestFixText(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(fix_text("""
            here is unchanged text
        """),
                         """
            here is unchanged text
        """)
        self.assertEqual(fix_text("""
            here is unchanged text with an unchanged url https://kryogenix.org
        """),
                         """
            here is unchanged text with an unchanged url https://kryogenix.org
        """)
        self.assertEqual(fix_text("""
            here is unchanged multiline text
            with an unchanged url
            https://kryogenix.org
            right here
        """),
                         """
            here is unchanged multiline text
            with an unchanged url
            https://kryogenix.org
            right here
        """)

    def test_changed(self):
        self.assertEqual(fix_text("""
            here is unchanged multiline text
            with a changed url
            https://kryogenix.org?utm_source=no
            right here
        """),
                         """
            here is unchanged multiline text
            with a changed url
            https://kryogenix.org
            right here
        """)
        self.assertEqual(fix_text("""
            here is unchanged multiline text
            with a changed url
            https://kryogenix.org?utm_source=no&a=1
            right here
        """),
                         """
            here is unchanged multiline text
            with a changed url
            https://kryogenix.org?a=1
            right here
        """)

    def test_with_tco(self):
        self.assertEqual(
            fix_text(
                "Go to https://t.co/pyzgkqT1xH?amp=1 for victory",
                handle_tco=True
            ),
            "Go to https://www.ietf.org/id/draft-schoen-intarea-unicast-127-00.html for victory"
        )
        self.assertEqual(
            fix_text(
                "Go to https://kryogenix.org for victory",
                handle_tco=True
            ),
            "Go to https://kryogenix.org for victory"
        )
        self.assertNotEqual(
            fix_text(
                "Go to https://kryogenix.org for victory",
                handle_tco=True
            ),
            "Go to https://kryogenix.org/ for victory" # extra slash: redirect NOT followed
        )


class TestContainsTco(unittest.TestCase):
    def test_simple_yes(self):
        self.assertTrue(contains_tco("https://t.co/abcde"))
        self.assertTrue(contains_tco("http://t.co/abcde"))
        self.assertTrue(contains_tco("This text contains https://t.co/abcde and others"))
        self.assertTrue(contains_tco("first: https://t.co/abcde, second: https://t.co/fghij, done"))
        self.assertTrue(contains_tco("first:\nhttps://t.co/abcde,\nsecond: https://t.co/fghij,\ndone"))

    def test_simple_no(self):
        self.assertFalse(contains_tco(""))
        self.assertFalse(contains_tco("Nope"))
        self.assertFalse(contains_tco("This text contains https://kryogenix.org and others"))
        self.assertFalse(contains_tco("https://at.co/123, https://no.t.co/123, t.co/123, all no"))


class TestFollowRedirects(unittest.TestCase):
    def test_examples(self):
        self.assertEqual(
            follow_redirects("https://t.co/pyzgkqT1xH?amp=1"),
            "https://www.ietf.org/id/draft-schoen-intarea-unicast-127-00.html")
        self.assertEqual(
            follow_redirects("https://kryogenix.org"), "https://kryogenix.org/")
        self.assertEqual(
            follow_redirects("https://kryogenix.org/"), "https://kryogenix.org/")


if __name__ == "__main__":
    unittest.main()