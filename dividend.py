from HTMLParser import HTMLParser
import urllib2
from datetime import date
import httplib

httplib.HTTPConnection._http_vsn = 10
httplib.HTTPConnection._http_vsn_str = 'HTTP/1.0'
currency_codes = open("currency_code_updated_4March2017.txt", "r").readlines()
currency_codes = [i.strip() for i in currency_codes]


class Parser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.recording = 0  # denotes if value is being recorded and the integer will determine which value is it currently
        self.row = 0
        self.year = 0
        self.details = 0
        self.checkdetails = 0
        self.data = {}
        self.currency = ''  # assuming company only pays dividends in one currency (no changes in currency of dividends)

    def handle_starttag(self, tag, attr):
        if tag == "div":
            for name, value in attr:
                if name == "id" and value == "dividendSummary":
                    self.row += 1
                if name == "id" and value == "details":
                    self.details += 1
        elif tag == "td" and self.row:
            self.recording += 1
        elif tag == "td" and self.details:
            self.checkdetails += 1

    def handle_endtag(self, tag):  # reset changed values
        if tag == "div":
            self.row = 0
        elif tag == "tr":
            self.recording = 0
        elif self.checkdetails == 5:
            self.checkdetails = 0  # resettings, just looking for 5th element of table, if not there then keep searching

    def handle_data(self, data):
        if data.strip():
            if self.recording == 1:
                self.year = int(data.strip())
            elif self.recording == 2:
                self.data[self.year] = float(data.strip())
            elif self.checkdetails == 5:  # we want the fifth element that shows amount of dividend and the currency, but just looking for the currency
                for i in data.split():
                    if i in currency_codes:  # ie if that piece of data is a currency code
                        self.currency = i
                        self.details = 0  # can exit the look

    def add_data(self, data, index):  # should not allow user to directly access data
        self.data[index] = data

    def return_data(self):
        return (self.data)

    def return_currency(self):
        return (self.currency)


def get_dividends(stock_codes):
    # stock_codes = json.load(open("short_stock_codes.json", "r"))     #need to run stock_codes.py
    # stock_codes = stockCodes.get_stock_codes()
    nodividends = sorted(stock_codes.keys())
    print(nodividends)
    dividends = {}
    while nodividends:
        # print ("hello")
        i = nodividends[0]
        if (i[-1].isdigit() or i[-2].isdigit() or '%' in i or '$' in i) or 'SEC' in i[-3:] or i[-1] == "A" or i[
            -1] == "R":  # all those with numbers at the back don't pay out dividends, either warrents, bonds or perpetual securities, later thinking of removing non-stocks from the stock list anyway
            del nodividends[0]
            continue  # alternatively bonds also have an A or R at the end, so need to check if all stocks do not have those at the end
        parser = Parser()
        url = "http://www.sgxdata.pebbleslab.com/index.asp?m=2&NC={0}".format(stock_codes[i])
        try:
            fileobj = urllib2.urlopen(url).read().decode("ISO-8859-1")
        except:
            continue
            # i have no idea, just that this works for some characters that can't be decoded by utf-8
        parser.feed(fileobj)
        try:  # this try part until the for loop is checking if the company has existed during the period when it didn't pay dividends, done so by checking if it has paid dividends before that period, just to make sure that company is in existence before concluding that it never paid dividend for that year (eg a company started in 2015 then records shows it never paid dividends before that, which is unfair towards it). This might make data look better as we assume that the company only existed when it paid its first dividends
            lowest_year = sorted(parser.data.keys())[0]  # seeing if company paid dividend before
        except IndexError:  # if company never paid a dividend before
            lowest_year = date.today().year + 1  # there may be an issue if the company is new
        else:
            lowest_year = sorted(parser.data.keys())[0]
        for j in range(lowest_year,
                       date.today().year + 1):  # must see if the company has paid before (it may not have existed in those years if it didn't pay), if it has paid then it must have existed
            if j not in parser.data:
                parser.add_data(0.0, j)
        dividend_data = parser.return_data()
        dividend_data["currency"] = parser.return_currency()
        dividends[stock_codes[i]] = dividend_data
        print ("{0:40s} {1}".format(i, parser.currency))
        del nodividends[0]
    return dividends

