from HTMLParser import HTMLParser
import urllib2
import json
import httplib

httplib.HTTPConnection._http_vsn = 10       #set up connection
httplib.HTTPConnection._http_vsn_str = 'HTTP/1.0'


class Parser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.price_targets = {}
        self.recording = 0
        self.full_data = []         #has a tendency to split at & so added this to collect the full data
        self.curr_target = None            #to store the data temporarily
        self.curr_date = None
        self.table = False              #checking if in correct table
        self.h3 = False                 #there are other occurences of Price Target in the data, but only one that is h3 tag
        self.adviser = None             #not actually required to store, but to prevent a space from taking over it, so that we can just take the first instance of this

    def handle_starttag(self, tag, attr):
        if tag == "td" and self.table:         #self.recording will be changed to 1 only after the Price Target header has been met
            self.recording += 1
        elif tag == "h3":             #take note if h3
            self.h3 = True

    def handle_data(self, data):
        if data == "Price Target" and self.h3:
            self.table = True
        elif self.recording == 1:
            if self.curr_date is None:
                self.full_data.append(data)
        elif self.recording == 3:             #will only refer to one element
            if self.curr_target is None:            #just take the first value (even through replaced the > < with ><, still seem to have some problems
                self.full_data.append(data)
        elif self.recording == 6:
            if self.adviser is None:   #the source is not quoted before, because we take the latest target from each source
                self.full_data.append(data)
                
    def handle_endtag(self, tag):
        if tag == "tr":
            self.recording = 0
            self.adviser = None     #resetting the values
            self.curr_target = None
            self.curr_date = None
        elif tag == "h3":           #reverse
            self.h3 = False
        elif tag == "table":            #remove the table part, the table is right after the h3 Price Target
            self.table = False
        elif self.recording == 1 and self.full_data is not []:      #not empty, so need to equate
            self.curr_date = ' '.join(self.full_data)
        elif self.recording == 3 and self.full_data is not []:
            self.curr_target = ' '.join(self.full_data)
        elif self.recording == 6 and self.full_data is not []:
            self.adviser = ' '.join(self.full_data)
            self.price_targets[str(self.adviser)] = [float(self.curr_target), str(self.curr_date)]
        if tag == "td":         #separate if-else cause need to do the top before clearing
            self.full_data = []

    def return_price_targets(self):
        return (self.price_targets)

    def average_price_target(self):    #to find simple average of all the price targets
        total = 0
        for i in self.price_targets.keys():
            total += self.price_targets[i][0]
        if len(self.price_targets) > 0:         #to prevent division by 0
            return (total / len(self.price_targets))
def get_price_targets(stock_codes):
    price_target_data = {}
    no_price_target = stock_codes.keys()

    while no_price_target:
        curr_stock = str(no_price_target[0])          #don't want unicode and just take the first from the array
        curr_name = stock_codes[curr_stock]
        if (curr_name[-1].isdigit() or curr_name[-2].isdigit() or '%' in curr_name or '$' in curr_name) or 'SEC' in curr_name[-3:] or curr_name[-1] == "A" or curr_name[-1] == "R":           #all those with numbers at the back don't pay out dividends, either warrents, bonds or perpetual securities, later thinking of removing non-stocks from the stock list anyway
            del no_price_target[0]
            continue        #alternatively bonds also have an A or R at the end, so need to check if all stocks do not have those at the end
        parser = Parser()
        url = "https://sgx.i3investor.com/servlets/stk/pt/{0}.jsp".format(curr_stock)
        try:                    #in case the conenction fails then just retry
            fileobj = urllib2.urlopen(url).read().decode("ISO-8859-1").replace('> <', '><')
        except:
            continue
        parser.feed(fileobj)
        price_targets = parser.return_price_targets()
        average = parser.average_price_target()
        if average != None:
            price_target_data[curr_stock] = {}
            price_target_data[curr_stock].update({"average": average})
            price_target_data[curr_stock].update(price_targets)
        del no_price_target[0]
        print (str(stock_codes[curr_stock]))          #for visual indication of progress
    return price_target_data
