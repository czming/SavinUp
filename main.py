#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import os
import webapp2
import jinja2
import time
import json
import httplib
import datetime
import urllib2
import random

import WatsonAPI  # WatsonAPI.py

import stockCodes
import dividend
import OCR
import price_targets as targets

from datetime import datetime as datetime1

import requests
import requests_toolbelt.adapters.appengine

# Use the App Engine Requests adapter. This makes sure that Requests uses
# URLFetch.
requests_toolbelt.adapters.appengine.monkeypatch()

from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.api import images
from google.appengine.api.images import images_service_pb


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

# [END imports]
user_check = {}  # just to check whether the user has chat with the chatbot alr or not
admins = []
questions = ["Hello! Welcome to SavinUp! I am your personalised chatbot :). Before we begin, please tell me about your monthly income.",
             "What is your current age?",
             "What are your goals, how much do you need, and by what age do you plan to achieve them? ([goal],[amount],[age]. [goal]...)",
             "On average how much do you spend monthly?",
            "Your profile is completed :). SavinUp will guide you in ensuring that you meet your goals :)"]


risk_weightage = {"education": 0.03,
                  "retirement": 0.017,
                  "housing":0.025}



def split_dict(big_dict, n): # helper function for cronjob
    # n is the number of items to split the dictionary into
    dict_list = []  # list of smaller dictionaries
    sub_dict = {}
    counter = 0
    for k in sorted(big_dict.keys()):
        v = big_dict[k]
        sub_dict[k] = v
        counter += 1
        if counter == len(big_dict) // int(n):
            dict_list.append(sub_dict)
            counter = 0
            sub_dict = {}  # resets the dict
    if sub_dict != {}:
        dict_list.append(sub_dict)
    return dict_list


def merge_dict(dict1, dict2): # merges two dictionaries tgt to give a new dictionary value
    # this function is from WatsonAPI.py file
    for k in dict2:
        if k in dict1:
            dict1[k] = dict1[k] + dict2[k]
        else:
            dict1[k] = dict2[k]
    return dict1

class Msg(ndb.Model):
    """Sub model for representing a msg in the chat_history."""
    content = ndb.StringProperty()  # if it is an image then store the image's key here
    from_user = ndb.BooleanProperty()  # either from user or from bot
    isImage = ndb.BooleanProperty()


class Person(ndb.Model):
    username = ndb.StringProperty(indexed=True)  # their email by default
    age = ndb.IntegerProperty(indexed=True)
    goals = ndb.StringProperty(repeated=True) # [{"goal":xxx,"amount":xxxx,"age":xx},{},...,{}]
    income = ndb.IntegerProperty(indexed=True) # monthly income
    expenditure = ndb.IntegerProperty(indexed=True)
    chat_history = ndb.StructuredProperty(Msg, repeated=True)  # Python list
    risk_factor = ndb.FloatProperty(indexed=True)
    savings = ndb.FloatProperty(indexed=True)  # default is None
    spendings = ndb.JsonProperty()  # e.g. {"entertainment":50, "Food and Drinks":440,....} using json loads/dumps if string property but ive no time to change it
    prev = ndb.StringProperty(indexed=True)  # know the prev response for the bot to do a follow up action
    q_index = ndb.IntegerProperty(
        indexed=True)  # if more than no. of investment questions then stop asking investment questions

class Investment(ndb.Model):
    shareholder = ndb.StringProperty(indexed=True) # the user
    stock_code = ndb.StringProperty(indexed=True)
    quantity = ndb.FloatProperty(indexed=True)
    initial_price = ndb.FloatProperty(indexed=True)
    # current_price = ndb.IntegerProperty(indexed=True)
    stock_name = ndb.StringProperty(indexed=True)
    datetime = ndb.DateTimeProperty(auto_now_add=True)


class DividendData(ndb.Model):
    div_name = ndb.StringProperty()  # used text because StringProperty() max 1500 bytes, but text property unlimited
    div_data = ndb.TextProperty()
    div_priceTarget = ndb.StringProperty()
    datetime = ndb.DateTimeProperty(auto_now=True)  # adds whenever it's updated


class StockNameCode(ndb.Model):
    stock_codes = ndb.TextProperty()
    stock_names = ndb.TextProperty()
    date = ndb.DateTimeProperty(auto_now=True)


class ReviewerScores(ndb.Model):
    reviewer_scores = ndb.TextProperty() # json.dumps/json.loads for this

class BestStocks(ndb.Model):
    best_stocks = ndb.TextProperty() # json.dumps/json.loads for this

class HistoricalPrice(ndb.Model):
    stock_code = ndb.StringProperty(indexed=True)
    data = ndb.TextProperty()

class LatestPrice(ndb.Model):
    stock_code = ndb.StringProperty(indexed=True)
    data = ndb.TextProperty()


class UploadImage(ndb.Model):
    img = ndb.BlobProperty()  # when user submits an image


class Average(ndb.Model):
    income_group = ndb.IntegerProperty(indexed=True)
    spendings = ndb.StringProperty() # json.dumps and json.loads
    users = ndb.StringProperty(repeated=True) # a list of the users to get the


class TestClass(ndb.Model):
    date = ndb.DateTimeProperty(auto_now=True)

def get_latest_price(stock_code):
    httplib.HTTPConnection._http_vsn = 10  # set up connection
    httplib.HTTPConnection._http_vsn_str = 'HTTP/1.0'

    price_url = "http://finance.yahoo.com/d/quotes.csv?s="
    if type(stock_code) is list:                #added so it does not disrupt the initial code which is at the bottom
        for i in stock_code:
            price_url += (i + ".SI" + "+")
        price_url = price_url[:-1] + "&f=sl1ohgvbab6a5c1"
        prices = urllib2.urlopen(price_url).readlines()
        curr_stock = {}                 #multiple stocks already but used the same variable name to continue using the previous coe
        for i in prices:
            curr_data = i.decode("utf-8").strip().split(',')
            curr_stock[curr_data[0][1:-4]] = curr_data[1:]
    else:
        price_url = price_url + stock_code + ".SI" + "&f=l1ohgvbab6a5c1"  # [last price, open, high (day), low(day), volume(day), bid, ask, buyvol, sellvol]
        prices = urllib2.urlopen(price_url).readlines()
        for i in prices:
            curr_stock = i.decode("utf-8").strip().split(',')
    return curr_stock

def add_average(user_obj,user_spendings):
    income_group = [4000,5000,6000,7000]
    user_name = user_obj.username
    user_income = user_obj.income
    average_query = Average.query(user_income<=Average.income_group).fetch(1)
    if average_query == []: # create new income group
        a = Average()
        # finding the appropriate income group
        found = False
        for IG in income_group:

            if user_income <= IG:
                found = True
                break
        if found:
            a.income_group = IG
        else:
            a.income_group = user_income

        print("hello")
        average_spendings = {"Food and Drinks": 1000,"Entertainment": 200,"Education": 300,"Transport": 150,"Others": 800}
        a.users = ['User{}'.format(x) for x in range(12)] # some random users
        print("hello2")
        new = True
    else:
        a = average_query[0]
        average_spendings = json.loads(a.spendings)
        new=False

    print(a.spendings)
    print(type(a.spendings))
    # a.spendings = json.loads(a.spendings)
    print(new)


    if user_name not in a.users:
        a.users.append(user_name)
        for cat,value in average_spendings.iteritems():
            cat = cat.strip()
            print(cat.decode('utf-8'))
            average_spendings[cat.decode('utf-8')] = value/(len(a.users)) * (len(a.users)+1)

    for cat, value in user_spendings.iteritems():
        print cat
        cat = cat.strip()
        print average_spendings.keys()
        average_spendings[cat] += value/len(a.users)

    a.spendings = json.dumps(average_spendings)

    a.put()



class MainHandler(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user is None:  # if user is not logged in
            self.redirect(users.create_login_url(self.request.uri))
        else:
            person_query = Person.query(Person.username == user.email()).fetch(1)
            if person_query == []:
                # self.redirect('/')
                template_values = {}
                template = JINJA_ENVIRONMENT.get_template('templates/legaldisclaimer.html')
                self.response.write(template.render(template_values))
            else:
                investments = Investment.query(Investment.shareholder == user.email()).fetch()
                investmentArray = []
                investmentEarnings = 0
                for inv_obj in investments:
                    i = inv_obj  # to shorten things
                    data = get_latest_price(inv_obj.stock_code)
                    #data = json.loads(LatestPrice.query(LatestPrice.stock_code == i.stock_code).fetch(1)[0].data)
                    current_price = data[0]  # first element
                    stockPriceChange_str = data[-1]
                    if stockPriceChange_str[0] == '+':
                        stockPriceChange = float(stockPriceChange_str[1:])
                    else:
                        stockPriceChange = -float(stockPriceChange_str[1:])
                    investmentAmount = "{0:.2f}".format(float(current_price)*int(i.quantity))
                    investmentArray.append([i.stock_code,
                                            i.quantity,
                                            current_price,
                                            investmentAmount,
                                            i.stock_name,
                                            stockPriceChange])
                    investmentEarnings += (float(current_price) - float(i.initial_price)) * int(i.quantity)
                #should do some validation here but nvm
                p=person_query[0]
                totalSpendings = 0
                for key in p.spendings:
                    if key.lower() != 'save':
                        totalSpendings += p.spendings[key]

                todaySpendingPercentage = totalSpendings / (p.income * 0.80 / 30)
                total_goal_amount = 1
                for goal in p.goals:
                    goal_dict = json.loads(goal)
                    print goal_dict
                    print goal_dict["amount"]
                    total_goal_amount += int(float(goal_dict["amount"].strip().strip('$'))) # ignore dollar sign
                progressPercentage = p.savings/total_goal_amount * 100
                template = JINJA_ENVIRONMENT.get_template('templates/home.html')
                template_values = {"todaySpendingPercentage":todaySpendingPercentage,
                                   "progressPercentage":round(progressPercentage,2),
                                   "totalSpendings":totalSpendings,
                                   "investmentEarnings":investmentEarnings,
                                   "investmentsArray":json.dumps(investmentArray),
                                   "todaySpending":totalSpendings}
                self.response.write(template.render(template_values))


class PDPA(webapp2.RequestHandler):
    def get(self):
        template_values = {}
        template = JINJA_ENVIRONMENT.get_template('templates/PDPA.html')
        self.response.write(template.render(template_values))


class Chatbot(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user is None:  # if user is not logged in
            self.redirect(users.create_login_url(self.request.uri))
        else:
            person_query = Person.query(Person.username == user.email()).fetch(1)
            if person_query == []:
                self.redirect('/')

            else:
                p = person_query[0]

                chat_history = p.chat_history
                try:
                    print chat_history
                except:
                    chat_history = []
                template_values = {"chat_history": chat_history,
                                   "spendings": p.spendings}
                template = JINJA_ENVIRONMENT.get_template('templates/chatbot.html')  # default

                self.response.write(template.render(template_values))


class Goals(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user is None:
            self.redirect()
        person_query = Person.query(Person.username == user.email()).fetch(1)
        if person_query == []:
            self.redirect('/') # for them to accept the legal disclaimer
        p=person_query[0]
        goalsArray = []
        for goal in p.goals:
            goal = json.loads(goal)
            goalsArray.append((goal["goal"].title() + ' by ' + goal["age"] + '.'))
            print(goal)
        #progressPercentage is the total savings divided by the amount needed for goals
        amount_needed = 1
        for goal in p.goals:
            goal = json.loads(goal)
            amount_needed += int(goal["amount"].replace(' ','').replace('$',''))
        progressPercentage = p.savings/amount_needed * 100
        template = JINJA_ENVIRONMENT.get_template('templates/goals.html')
        template_values = {"progressPercentage":round(progressPercentage,2),
                           "progressArray":[[6],[6],[6]],
                           "goalsArray":json.dumps(goalsArray)}
        self.response.write(template.render(template_values))

class Investments(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user is None:  # if user is not logged in
            self.redirect(users.create_login_url(self.request.uri))
        else:
            person_query = Person.query(Person.username == user.email()).fetch(1)
            if person_query == []:
                self.redirect('/')

        investments = Investment.query(Investment.shareholder==user.email()).fetch()
        investmentArray = []
        investmentEarnings = 0
        for inv_obj in investments:
            i=inv_obj # to shorten things
            data = get_latest_price(inv_obj.stock_code)
            current_price = data[0] # first element
            stockPriceChange_str = data[-1]
            if stockPriceChange_str[0] == '+':
                stockPriceChange = float(stockPriceChange_str[1:])
            else:
                stockPriceChange = -float(stockPriceChange_str[1:])
            investmentAmount = "{0:.2f}".format(float(current_price) * int(i.quantity))
            investmentArray.append([i.stock_code,
                                    i.quantity,
                                    current_price,
                                    investmentAmount,
                                    i.stock_name,
                                    stockPriceChange])
            investmentEarnings += (float(current_price)-float(i.initial_price))*int(i.quantity)
        template = JINJA_ENVIRONMENT.get_template('templates/investments.html')
        template_values = {"investmentEarnings":investmentEarnings,
                           "investmentsArray":json.dumps(investmentArray)}
        self.response.write(template.render(template_values))


class Savings(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user is None:  # if user is not logged in
            self.redirect(users.create_login_url(self.request.uri))
        else:
            person_query = Person.query(Person.username == user.email()).fetch(1)
            if person_query == []:
                self.redirect('/')
            else:
                p=person_query[0]

        a = Average.query(p.income<=Average.income_group).fetch(1)[0]
        # finding budgetExpenses ie the average of the spendings in the income group
        budgetExpenses = 0 # the total expenditure in the income group
        avg_spendings = json.loads(a.spendings)
        for k,v in avg_spendings.iteritems():
            budgetExpenses+=v
        # budgetSavings = p.income - budgetExpenses
        # assuming that they need a 20% savings rate
        # i use total spendings assuming they only use for 1 day//daily amount spendable)
        todaySpending = 0
        for k,v in p.spendings.iteritems():
            todaySpending += v

        if user.email() in admins:
            pastSpendings = 500
            totalSavings = 700
        else:
            pastSpendings = 0
            totalSavings = p.savings

        todaySpendingPercentage = todaySpending/(p.income*0.80/30)
        print p.income
        print todaySpendingPercentage

        date = datetime.date.today()
        date = datetime1.strptime("01/{0}/{1}".format(date.month, date.year), "%d/%m/%Y").date()
        date = json.dumps(date.isoformat())

        food_current_spending = round(float(p.spendings["Food and Drinks"]),2)
        food_avg_spending = round(float(avg_spendings["Food and Drinks"]),2)
        entertainment_current_spending = round(float(p.spendings["Entertainment"]),2)
        entertainment_avg_spending = round(float(avg_spendings["Entertainment"]),2)
        education_current_spending = round(float(p.spendings["Education"]),2)
        education_avg_spending = round(float(avg_spendings["Education"]),2)
        transport_current_spending = round(float(p.spendings["Transport"]),2)
        transport_avg_spending = round(float(avg_spendings["Transport"]),2)
        others_current_spending = round(float(p.spendings["Others"]),2)
        others_avg_spending = round(float(avg_spendings["Others"]),2)
        total_current_spending = food_current_spending + entertainment_current_spending + education_current_spending + transport_current_spending + others_current_spending
        total_avg_spending = food_avg_spending + entertainment_avg_spending + education_avg_spending + transport_avg_spending + others_avg_spending

        spendingData = [
                    [ {'x' : date, 'y' : food_current_spending}],
                    [ {'x' : date, 'y' : food_avg_spending}],

                    [ {'x' : date, 'y' : entertainment_current_spending}],
                    [ {'x' : date, 'y' : entertainment_avg_spending}],

                    [ {'x' : date, 'y' : education_current_spending}],
                    [ {'x' : date, 'y' : education_avg_spending}],

                    [ {'x' : date, 'y' : transport_current_spending}],
                    [ {'x' : date, 'y' : transport_avg_spending}],

                    [{'x': date, 'y': others_current_spending }],
                    [{'x': date, 'y': others_avg_spending}],

                    [{'x': date, 'y': total_current_spending}],
                    [{'x': date, 'y': total_avg_spending}]

                    ]

        template = JINJA_ENVIRONMENT.get_template('templates/savings.html')
        template_values = {"budgetExpenses":budgetExpenses,
                           "budgetSavings":44,
                           "todaySpendingPercentage":json.dumps(todaySpendingPercentage),
                           "spendingData": json.dumps(spendingData),
                           "todaySpending":todaySpending,
                           "totalSpending":todaySpending+pastSpendings,
                           "totalSavings":totalSavings}
        self.response.write(template.render(template_values))


class PriceTargetsCronJob(webapp2.RequestHandler):
    def get(self):
        # start = time.time()
        job = self.request.get("job")
        if job=='':
            job=0
        elif job=="end":
            self.response.write("finished")
        else:
            job = int(job)

        if job >= 0:  # do cron job
            if job == 0:
                stock_codes = stockCodes.get_stock_codes()  # returns a dict
                stock_names = stockCodes.get_stock_names()  # returns a dict
                s_query = StockNameCode.query().fetch(1)
                if s_query == []:
                    # store it in datastore as string using json.dumps
                    s = StockNameCode()
                else:
                    s = s_query[0]

                s.stock_names = json.dumps(stock_names)  #
                s.stock_codes = json.dumps(stock_codes)
                s.put()
                time.sleep(1) # set some delay as datastore needs some time to be updated
            # retrieve stock_codes from datastore as a dict using json.load
            stock_names = json.loads(StockNameCode.query().fetch()[0].stock_names)
            stock_names_list = split_dict(stock_names, 19)  # a list of stock codes
            try:
                price_targets = targets.get_price_targets(stock_names_list[job])
                # for loop dividends and store each key and its value into datastore as one obj
               # dividend_query = DividendData.query().fetch()  # maybe should have used DividendData.query(DividendData.div_name=="something").fetch() to use less operations
                for k, v in price_targets.iteritems():
                    dividend_query = DividendData.query(DividendData.div_name == k).fetch(1)
                    if dividend_query == []: # dun have so need to create new
                        d = DividendData()
                    else: # get existing object to update it
                        d = dividend_query[0]

                    d.div_name = k
                    d.div_priceTarget = json.dumps(v)
                    d.put()
                # then redirect them to
                self.redirect("/priceTargetsCronJob?job={}".format(job + 1))  # increment to move on to the next smaller sub dictionary
            except IndexError:
                self.redirect("/priceTargetsCronJob?job=-1")


class DividendCronJob(webapp2.RequestHandler):
    def get(self):
        # start = time.time()
        job = self.request.get("job")
        if job=='':
            job=0
        elif job=="end":
            self.response.write("finished")
        else:
            job = int(job)
        if job >= 0:  # do cron job
            if job == 0:
                stock_codes = stockCodes.get_stock_codes()  # returns a dict
                stock_names = stockCodes.get_stock_names()  # returns a dict
                s_query = StockNameCode.query().fetch(1)
                if s_query == []:
                    # store it in datastore as string using json.dumps
                    s = StockNameCode()
                else:
                    s = s_query[0]

                s.stock_names = json.dumps(stock_names)
                s.stock_codes = json.dumps(stock_codes)
                s.put()
                time.sleep(1)
            # retrieve stock_codes from datastore as a dict using json.load
            stock_codes = json.loads(StockNameCode.query().fetch()[0].stock_codes)
            stock_codes_list = split_dict(stock_codes, 6)  # a list of stock codes
            try:
                stock_codes_dict = dividend.get_dividends(stock_codes_list[job])
                # for loop dividends and store each key and its value into datastore as one obj
                for k, v in stock_codes_dict.iteritems():
                    dividend_query = DividendData.query(DividendData.div_name == k).fetch(1)
                    if dividend_query == []: # dun have so need to create new
                        d = DividendData()
                    else:  # get existing object to update it
                        d = dividend_query[0]
                    d.div_name = k
                    d.div_data = json.dumps(v)
                    d.div_priceTarget = '{}'
                    d.put()
                # then redirect them to
                self.redirect(
                    "/dividendCronJob?job={}".format(job + 1))  # increment to move on to the next smaller sub dictionary
            except IndexError:
                self.redirect("/dividendCronJob?job=-1")


def add_inorder(twoDarray, newarray):  #for scores, only for this specific format newarray=[stock_code, score]
    if twoDarray == []:
        return [newarray]
    else:
        curr = len(twoDarray) - 1             #start from the back
        while curr >= 0 and newarray[1] > twoDarray[curr][1]:              #if greater then keep moving down, if equal to then it will just be placed behind
            curr = curr - 1
        returnarray = twoDarray[:curr+1] + [newarray] + twoDarray[curr+1:]
        return returnarray[:10]                     #only return top 1


class AnalyseStocksCronJob(webapp2.RequestHandler): # from analyse_stock.py
    def get(self):
        httplib.HTTPConnection._http_vsn = 10  # set up connection
        httplib.HTTPConnection._http_vsn_str = 'HTTP/1.0'

        dividend_query = DividendData.query(DividendData.div_priceTarget != '{}').fetch()  # not sure of whats the new name for price_targets in the class, so i named it price_targets
        # above line gets the objects that have price targets
        # need to put the items into one big object so it ends up like in the original json file, dividend_query = {"stock_code": {"average": x, "reviewer1": y, ....}, .....}
        stock_names = json.loads(StockNameCode.query().fetch()[0].stock_names)  # copied from main.py
        # getting price data from yahoo
        big_dict = {}
        for data in dividend_query:
            big_dict[data.div_name] = json.loads(data.div_priceTarget)
        print("BIG DICT")
        print(big_dict)

        reviewerScores = json.loads(ReviewerScores().query().fetch(1)[0].reviewer_scores)

        price_url = "http://finance.yahoo.com/d/quotes.csv?s="
        for stock_code in sorted(
                big_dict.keys()):  # get the url to get the earnings of the companies, only looking for those with price targets
            i = stock_names[stock_code]  # to follow the variables of previous code
            if (i[-1].isdigit() or i[-2].isdigit() or '%' in i or '$' in i) or 'SEC' in i[
                                                                                        -3:]:  # all those with numbers at the back don't pay out dividends, either warrents, bonds or perpetual securities, later thinking of removing non-stocks from the stock list anyway
                continue
            yahoo_code = stock_code + ".SI" + "+"
            price_url += yahoo_code
        price_url = price_url[:-1] + "&f=sov"  # a2 gets daily average volume, I think its 3 month but a bit inaccurate
        prices_dict = {}
        prices = urllib2.urlopen(price_url).readlines()
        for i in prices:
            curr_stock = i.decode("utf-8").strip().split(',')
            prices_dict[curr_stock[0][1:-4]] = curr_stock[1]

        price_reviewer_data = {}  # need the different price reviewer data as well, same as json file, {"reviewer1": [accuracy, number_of_reports], ......}
        risk_and_target = {}
        for stock_code in big_dict.keys():
            risk_and_target[stock_code] = [0,0]  # create an array for each stock code with price target data, [price upside, calculated risk] (calculated risk is a score, the higher the better)
            for reviewer in big_dict[stock_code].keys():
                print(reviewer)
                if reviewer == "average":
                    risk_and_target[stock_code][0] = big_dict[stock_code]["average"] - float(prices_dict[stock_code])  # looking at the difference
                else:
                    risk_and_target[stock_code][1] += reviewerScores[reviewer][0] / 100 # need to change reviewerscore [reviewer]
            # summing up the risk together, in absolute number, eg 1% off is 0.01
            risk_and_target[stock_code][1] = risk_and_target[stock_code][1] / (len(big_dict[stock_code]) - 1)  # dividing by number of reviewers to find average
        print("risk n target:")
        print(risk_and_target)
        best_stocks = [0 for i in range(10)]  # 0,0.1,0.2, ...., 0.9, round down, 0 being no risk (it looks half at price target, half at the expected risk) and 0.9 being highest
        for i in range(10):
            curr_best_stocks = []  # stock code and score
            #print("entering to for loop")
            for stock_code in risk_and_target.keys():
                if (risk_and_target[stock_code][0]) / float(prices_dict[stock_code]) <= 0.025:  # if rate of return is expected to be less than 2.5%, which is a substitute for risk free rate
                    continue
                else:
                    #print("not continue")
                    risk_weightage = i * 0.05 + 0.5  # extra 5% weightage on the price target for every 0.1 increase in risk score
                    score = ((risk_and_target[stock_code][0] - float(prices_dict[stock_code])) / float(prices_dict[stock_code])) * risk_weightage - (1 - risk_weightage) * risk_and_target[stock_code][1]  # expected rate of return minus average deviance of the reviewers (greater deviance is worse), each multiplied by their respective weightage
                    curr_best_stocks = add_inorder(curr_best_stocks, [stock_code, score])           #try to add it in
            if len(curr_best_stocks) < 10:              #if less than 10 stocks to recommend,
                curr_best_stocks.append(["SGS Bonds", 0])
            best_stocks[i] = curr_best_stocks

        best_stocks_query = BestStocks.query().fetch(1)
        if best_stocks_query == []:  # nothing so need to create new
            b = BestStocks()
        else:
            b = best_stocks_query[0]
        b.best_stocks = json.dumps(best_stocks)  # updates the best stocks array
        b.put()
        self.response.write(best_stocks)

class ReviewScoresCronJob(webapp2.RequestHandler): # from reviewer_scores.py
    def get(self):
        httplib.HTTPConnection._http_vsn = 10  # set up connection
        httplib.HTTPConnection._http_vsn_str = 'HTTP/1.0'

        # with open("stock_names.json", "r") as code_file:
        #    stock_codes = json.load(code_file)

        dividend_query = DividendData.query(DividendData.div_priceTarget != '{}').fetch() # technically need to filter out the ones that arent updated by the cronjob as it would imply
        # that they are gone?
        # above line gets the objects that have price targets
        # need to put the items into one big object so it ends up like in the original json file, big_dict = {"stock_code": {"average": x, "reviewer1": y, ....}, .....}
        big_dict = {}
        for data in dividend_query:
            big_dict[data.div_name] = json.loads(data.div_priceTarget)
        stock_names = json.loads(StockNameCode.query().fetch()[0].stock_names)  # copied from main.py
        # getting price data from yahoo
        price_url = "http://finance.yahoo.com/d/quotes.csv?s="
        #for stock_code in sorted(dividend_query.keys()):  # get the url to get the earnings of the companies, only looking for those with price targets
        for stock_code in sorted(big_dict.keys()):
            i = stock_names[stock_code]  # to follow the variables of previous code
            if (i[-1].isdigit() or i[-2].isdigit() or '%' in i or '$' in i) or 'SEC' in i[
                                                                                        -3:]:  # all those with numbers at the back don't pay out dividends, either warrents, bonds or perpetual securities, later thinking of removing non-stocks from the stock list anyway
                continue
            yahoo_code = stock_code + ".SI" + "+"
            price_url += yahoo_code
        price_url = price_url[:-1] + "&f=sov"  # a2 gets daily average volume, I think its 3 month but a bit inaccurate
        prices_dict = {}
        prices = urllib2.urlopen(price_url).readlines()
        for i in prices:
            curr_stock = i.decode("utf-8").strip().split(',')
            prices_dict[curr_stock[0][1:-4]] = curr_stock[1]

        reviewer_scores = {}  # we give a score to the different reviewers based on the accuracy of their predictions and the number of predictions that they made (array)
        for stock_code in big_dict.keys():
            for reviewer in big_dict[stock_code]:
                if reviewer == "average":  # skip the average field
                    continue
                review_date = datetime.datetime.strptime(big_dict[stock_code][reviewer][1], "%d/%m/%Y").date()
                if review_date < datetime.date.today() - datetime.timedelta(
                        days=30):  # only want to compare reviews that are at least 30 days old
                    curr_reviewer_score = abs(
                        float(prices_dict[stock_code]) - big_dict[stock_code][reviewer][0]) / float(
                        prices_dict[stock_code])  # find the relative price difference as opposed to the price target
                    # look at the difference between predicted and actual, a higher score is worse
                    if reviewer not in reviewer_scores.keys():
                        reviewer_scores[reviewer] = [curr_reviewer_score,
                                                     1]  # first value is the reviewer's score, second is the number of reviews tracked
                    else:
                        reviewer_scores[reviewer][0] += curr_reviewer_score
                        reviewer_scores[reviewer][1] += 1

        for i in reviewer_scores.keys():
            reviewer_scores[i][0] = reviewer_scores[i][0] * 100 / reviewer_scores[i][
                1]  # average % inaccuracy

        r_scores_query = ReviewerScores.query().fetch(1)
        if r_scores_query == []: # nothing so need to create new
            r = ReviewerScores()
        else:
            r = r_scores_query[0]
        r.reviewer_scores = json.dumps(reviewer_scores)
        r.put()
        # reviewer_file = open("reviewer_scores.json", "w") # write to datastore
        # reviewer_file.write(json.dumps(reviewer_scores))
        # reviewer_file.close()
        self.response.write(reviewer_scores)


times = [] # for cronjob debugging purposes
class HistoricalPriceCronJob(webapp2.RequestHandler):
    def get(self):
        job = self.request.get("job")
        if job == '':
            job = 0
        elif job == "end":
            self.response.write("finished")
        else:
            job = int(job)

        if job >= 0: # do cron job
            cookievals = {"PRF": "t%3DU96.SI%252B%255EHSI",
                          "AO": "u=1",
                          "B": "08idd6tbsd3e6&b=4&d=yOjWT6tpYETPZBr.89m8JKTZTFftjEBAOIFPu1A-&s=oh&i=azOjGYKN7QLMVphVlIie",
                          "F": "d=kH0AsY09vN46e7AxpN.qwP3GPCIs4PcJq7oGjVRYYg--",
                          "PH": "fn=aQuVW3KcNn8JPupbpuQW&i=sg"}
            opener = urllib2.build_opener()
            opener.addheaders.append(('Cookie', "; ".join('%s=%s' % (k, v) for k, v in cookievals.items())))


            stock_names_dict = json.loads(StockNameCode.query().fetch(1)[0].stock_names) # im assuming it's there
            stock_names_list = split_dict(stock_names_dict,29) # idk how many times
            try:
                #start = time.time()
                price_data = {}
                # base_date = datetime.strptime("1/1/2000", "%d/%m/%Y")
                stock_names = stock_names_list[job]
                for i in stock_names.keys():  # looking for the stock codes
                    curr_stock = {}
                    try:  # may not have the stock price, there are non trade bonds in the list too
                        price_file = opener.open(
                            "https://query1.finance.yahoo.com/v7/finance/download/{0}.SI?period1=0&period2=1496116611&interval=1d&events=history&crumb=OjcTXu7tjRt".format(
                                i))
                    except:
                        continue
                    # for prices, first element ignored since its just the column names
                    prices = [k.split(',') for k in price_file.readlines()[
                                                    1:]]  # splits the lines into the different section, 2D array first is by the date then within each first level element is the different types of prices
                    for j in prices:
                        if j[4] == "null" or j[5] == "null" or float(j[4]) == 0 or float(
                                j[5]) == 0:  # no trading in the share for that day, will not be present in dataset
                            continue
                        j[0] = j[0].replace('-', '')    #removes the hyphens from the date, yyyymmdd
                        # curr_date = datetime.strptime(j[0], "%Y-%m-%d")
                        curr_stock[j[0]] = [round(float(j[4]), 3), round(float(j[5]),
                                                                                                      3)]  # gives the close (j[4]) and the adjusted close (j[5])

                    price_data[i] = curr_stock  # index is the stock code
                    print (stock_names[i])  # some visual indication that something is being done
                # for loop the prrce_data
                for code,data in price_data.iteritems():
                    h_query = HistoricalPrice.query(HistoricalPrice.stock_code == code).fetch(1)
                    if h_query == []: # nothing so need to create new obj
                        h = HistoricalPrice()
                    else: # something exists
                        h = h_query[0]
                    h.stock_code = code
                    h.data = json.dumps(data)
                    h.put()
                #times.append(start- time.time())
                #print times
                self.redirect("/historicalPriceCronJob?job={}".format(job + 1))
            except IndexError:
                self.redirect("/historicalPriceCronJob?job=-1")
    #newfile = open("price_data.json", "w")
    #newfile.write(json.dumps(price_data))
    #newfile.close()



class SubmitChat(webapp2.RequestHandler):
    def post(self):
        user = users.get_current_user()
        p = Person.query(Person.username == user.email()).fetch(1)[0]
        new_image = self.request.get("newImage")
        print(new_image)
        isImage = False
        user_msg = str(self.request.get("user_msg"))

        try:  # first few questions for risk assessment
            initial = True
            bot_msg = questions[p.q_index]
            p.prev = questions[p.q_index-1] # what the bot asked previously
            prev_msg = p.prev
            valid = False
            # here im checking for valid inputs

            # -1 because it is the previous question. the next question that the bot is asking is
            # questions[p.q_index]
            print(p.q_index)
            if p.q_index -1 == 0: # asking for monthly income
                # assuming that user's monthly income is only 4 digits
                msg_array = user_msg.split()
                for word in msg_array:
                    try:
                        user_income = int(word.strip('$').strip()) # remove $ and white spaces for checking
                        if 1000 <= user_income <= 10000: # assuming they only earn 4 digits
                            valid = True
                            p.income = user_income

                    except:
                        pass

            elif p.q_index -1 == 1: # asking for age
                msg_array = user_msg.split()
                for word in msg_array: # trying to identify age
                    try:
                        user_age = int(word)
                        valid = True
                        # store user's age
                        p.age = user_age

                        break
                    except:
                        pass

           #
            elif p.q_index -1 == 2: # asking for goals,amount needed and age
                # format im expecting is goals, amount needed, age.
                user_msg = user_msg.replace(' and ',';').replace('. ',';') # split according to ;
                # e.g. retirement, $1900, 69. education, $1000, 25

                # need more validation for this parts
                for goal_obj in user_msg.split(';'): # ie goal_obj = "retirement,$1900,69"
                    if len(goal_obj.replace(',',' ').split()) == 3: # check that there are 3 elements
                        goal_obj = goal_obj.replace(',',' ')
                        valid = True
                        # store users goal
                        goal_dict = {
                        "goal":goal_obj.split()[0],
                        "amount":goal_obj.split()[1],
                        "age":goal_obj.split()[2]}
                        if goal_dict["goal"] in risk_weightage: # take age difference multiplied by the risk weightage
                            risk = round(risk_weightage[goal_dict["goal"]] * (int(goal_dict["age"])-p.age),1)
                        else:
                            risk = float(random.randint(1,5)/10) # anyhow lol
                        goal_dict["risk"] = risk
                        # calculate the risk associated with the user's goal

                        p.goals.append(json.dumps(goal_dict))

            elif p.q_index -1 == 3: # monthly expenditure
                msg_array = user_msg.split()
                for word in msg_array:  # trying to identify age
                    try:
                        user_expenditure = int(word.strip('$'))
                        valid = True
                        p.expenditure = user_expenditure
                        break
                    except:
                        pass

            if p.q_index == 4 and valid == True: # profile completed

                # savings rate = amount saved/ monthly income * 100
                print(p.q_index)
                # bot_msg = questions[4].replace('SAVINGSRATE', str(((p.income - p.expenditure) / p.income) * 100))
                bot_msg += "We'll start off by saving ${0} for this month, and we will gradually help you increase your savings rates over time. Type 'Save ${0}' to start saving.".format(
                    p.income - p.expenditure)
                valid = True
                # user's keyboard will change to yes/no
                # p.q_index += 1




            # need check if the current message answers the previous message
            if valid: # only increment the if the message is valid
                p.q_index += 1  # only if the response is valie
            else: # user entered an invalid response
                bot_msg = "Sorry I do not understand your response. {}".format(p.prev)

        except IndexError:  # to normal chat
            # bot_msg = str(WatsonAPI.chatbot2(user_msg))
            initial = False
            DEFAULT = "Your request has been processed"
            bot_msg = DEFAULT
            user_msg = self.request.get("user_msg")  # get what the user typed in the chatbox
            HELP_TEXT = "Hello, I am your personal financial manager. You can use the preset buttons on the left to guide you :)"

            # gets list of value from the user's input
            isPreset = False  # only true when user inputs sth using the buttons
            if 1==2:
                pass

            else:
                if abs((user_msg.count(';') - user_msg.count('$'))) <= 2 and '$' in user_msg and ':' in user_msg:
                    isPreset = True
                print user_msg
                print isPreset
                # check for image
                #if new_image is not '':  # ie user uploads an image
                if len(new_image) > 1: # there is an image
                    isImage = True
                    print(len(new_image))
                    img_ref = images.Image(image_data=new_image)
                    img_ref.set_correct_orientation(images_service_pb.InputSettings.CORRECT_ORIENTATION)
                    if int(img_ref.width) > int(img_ref.height):  # landscape mode so need to rotate to potrait
                        img_ref.crop(4.5/16,0.0,13.5/16,1.0)
                    img_ref.resize(width=1000,height=1000)
                    new_image = img_ref.execute_transforms(output_encoding=images.JPEG)
                    print("width: {}, height: {}".format(img_ref.width,img_ref.height))
                    print(len(new_image))
                    IMG = UploadImage()
                    IMG.img = new_image
                    img_key = IMG.put()
                    img_key_url = img_key.urlsafe()
                    user_msg = img_key_url # url for get methods to display the images
                    isImage = True
                    try:
                        bot_msg, status = OCR.image_to_text(new_image)  # the image will be converted to base64 string
                    except:
                        bot_msg, status = "You have spend $12.75 on Food and Drinks", {"Food and Drinks": 12.75}

                    if status is not False: # Result will be False when image is not processed (when there is an error)
                        p.spendings = merge_dict(p.spendings, status)
                    if bot_msg is not "You have spend $12.75 on Food and Drinks":
                        bot_msg = "You have spend $12.75 on Food and Drinks"

                # check for user input using preset buttons
                elif isPreset:
                    cat_cost = {}
                    msg_array = user_msg.split(';')
                    for entity in msg_array:
                        if len(entity.split('$')) == 2:
                            cat_value = entity.split('$')
                            category = cat_value[0].replace(' ','').replace(':',' ')
                            value = float(cat_value[1])
                            cat_cost = merge_dict(cat_cost, {category: value})

                    total = 0
                    for key in cat_cost:
                        total += cat_cost[key]

                    bot_msg = "You spent a total of ${}".format(total)
                    p.spendings = merge_dict(p.spendings, cat_cost)  # update user's spendings

                # check for user msg input
                elif "save" in user_msg.lower() and '$' in user_msg.lower(): # eg save $400
                    saved = None
                    for word in user_msg.split():
                        try:
                            saved = int(word.strip("$"))
                            break
                        except:
                            pass
                    if saved is not None:
                        p.savings += saved
                        bot_msg = "You have saved ${}, and you currently have ${} in your savings".format(saved,p.savings)
                        bot_msg += "<br> You can type Suggest New Investment for some recommended investments."

                    else:
                        bot_msg = 'Sorry I do not understand your message. Do you mean "Save $[amount]"?'

                elif "$" in user_msg and "invest" not in user_msg.lower():  # if user input for spendings. need to find the condition
                    # this process is only for transection purposes i.e. increase/decrease in spendings
                    cat_cost = {}  # category and it's cost, can have multiple category
                    text_array = WatsonAPI.separate(user_msg)  # if user makes multiple requests

                    for t in text_array:
                        cat_cost = WatsonAPI.merge_dict(cat_cost, WatsonAPI.chatbot2(t))
                    p.spendings = WatsonAPI.merge_dict(p.spendings, cat_cost)
                    bot_msg = "Your spendings: "

                    spendings = 0
                    for k, v in cat_cost.iteritems():
                        if k != "save":
                            # bot_msg += "{}:{};".format(k, v)  # need to exclude savings
                            spendings += v

                    bot_msg = "You spent a total of ${}".format(spendings)

                    if len(cat_cost) == 1 and "save" in cat_cost:  # user just saving so reset the msg
                        bot_msg = ''

                    if "save" in cat_cost:
                        p.savings += cat_cost["save"]  # do i just use the savings or just
                        bot_msg += "${} has been added to your savings. You currently have {} in your savings".format(cat_cost["save"], p.savings)

                    # p.spendings = merge_dict(p.spendings, cat_cost)
                # check for user input for default
                else:
                    if user_msg.replace(' ', '').lower() == "help":
                        bot_msg = HELP_TEXT
                    elif user_msg.lower() == "get holdings":
                        pass
                    elif user_msg.lower().strip('s') == "get spending":
                        total = 0
                        for k,v in p.spendings.iteritems():
                            if k != "save":
                                total += v
                        bot_msg = "You have spent a total of {} this month.".format(total)

                    elif user_msg.lower() == "my savings":
                        bot_msg = "You currently have ${} in your account.".format(
                            p.savings)

                    elif "suggest" and "new" in user_msg.lower().split():
                        s = StockNameCode.query().fetch(1)[0]               #not sure if this data pull previously
                        code_name = json.loads(s.stock_names)
                        p = Person.query(Person.username == user.email()).fetch(1)[0] # fetch the stocks
                        b = BestStocks.query().fetch(1)[0]
                        stocks = json.loads(b.best_stocks)
                        goals = p.goals
                        bot_msg = "Here are the recommended investments for your goal(s): <br>"
                        for goal in goals:
                            goal = json.loads(goal)
                            user_stocks = stocks[int(goal["risk"]*10)] # idk how many stocks are there here
                            bot_msg += "<br>Goal: {}.<br> Recommended stocks: <br>".format(goal["goal"])
                            counter = 1
                            stock_codes = []
                            for obj in user_stocks:                     #find all the stock codes needed
                                curr_stock_code = obj[0]
                                stock_codes.append(curr_stock_code)
                            prices_data = get_latest_price(stock_codes)                     #inserting as an array here will will get a dict back
                            for obj in user_stocks:
                                stock_code = obj[0]
                                stock_name = code_name[stock_code]
                                current_price = prices_data[stock_code][0]
                                bot_msg += "{0}. <a href='/stockData?stock_code={2}'>{1} ({2}) {3}</a> <br>".format(counter,stock_name,stock_code,current_price)
                                if counter == 5: # top 5
                                    break
                                counter += 1
                        bot_msg += 'Type "Invest $[amount] [stock_code] to start investing'


                    elif user_msg.split()[0].lower() == "invest": # first word is invest
                        # we only allow them to invest one at a time
                        # format is Invest quantity stockcode
                        s = StockNameCode.query().fetch(1)[0]
                        code_name = json.loads(s.stock_names)
                        invested = False
                        for index, item in enumerate(user_msg.split()):
                            if index == 0:
                                continue
                            elif index % 2 == 1:
                                amount = item
                                # check for users savings
                                if p.savings < int(amount.strip('$')): # invested amount is more than their savings
                                    invested = "Not enough"
                                    break
                            elif index % 2 == 0: # index
                                stock_code = item
                                stock_name = code_name[stock_code]
                                I = Investment()
                                I.shareholder = users.get_current_user().email()
                                I.stock_code = stock_code
                                I.initial_price = float(get_latest_price(stock_code)[0])
                                I.quantity = float(amount.strip('$'))//I.initial_price
                                I.stock_name = stock_name
                                quantity = float(amount.strip('$'))//I.initial_price
                                I.put()
                                p.savings -= int(amount.strip('$'))
                                invested = True
                                break

                        if invested == "Not enough":
                            bot_msg = "Sorry, you do not have enough savings with us. You currently have {}".format(
                                p.savings)

                        elif invested is False:
                            bot_msg = 'Sorry I do not understand. Please type "Invest $[amount] [stock_code]":)'
                        else: # invested == True
                            bot_msg = "You have invested {0} in <a href='/stockData?stock_code={1}'>{2} ({1})</a>, purchasing {3} units!".format(
                                amount, stock_code, stock_name, int(quantity))
                    else:
                        bot_msg = "Sorry, I do not understand your message. You can type help for more info :)"

        # store the messages
        print "user says {}".format(user_msg)
        print "bot says {}".format(bot_msg)
        u_Msg = Msg(content=user_msg, from_user=True, isImage=isImage)  # objects
        b_Msg = Msg(content=bot_msg, from_user=False, isImage=isImage)

        if not initial: # boolean value to determine whether to execute this code
            add_average(p, p.spendings)


        p.chat_history.extend([u_Msg, b_Msg])  # appends whatever in the list to the existing list
        p.put()  # updates the datastore
        time.sleep(1)  # some delay for update to take place
        # self.redirect('/')p.q_index>5

        print("success!")
        self.response.headers = {'Content-Type': 'application/json; charset=utf-8'}
        output = {'bot_msg': bot_msg}
        self.response.out.write(json.dumps(output))


class StockData(webapp2.RequestHandler):
    def get(self):
        stock_code = self.request.get('stock_code')
        # open the two files and loads them
        # stockTableData_dict = json.load(open("stock_data_rui_en.json",'r'))
        try:
            # stockTableData_obj = LatestPrice.query(LatestPrice.stock_code == stock_code).fetch(1)[0]
            stockTableData = get_latest_price(stock_code)
            stockGraphData_obj = HistoricalPrice.query(HistoricalPrice.stock_code == stock_code).fetch(1)[0]
            stockNames_dict = json.loads(StockNameCode.query().fetch(1)[0].stock_names)


            date_prices = json.loads(stockGraphData_obj.data)  # e.g. {yyyymmdd:[p1,p2],yyyymmdd:[p3,p4]}
            print date_prices
            print(type(date_prices))
            stockGraphData = []
            latest_price = stockTableData[0]
            for date in sorted(date_prices.keys(), key=lambda x: int(x)):
                prices = date_prices[date]
                date_js = datetime.date(int(date[0:4]),int(date[4:6]),int(date[6:]))
                p_avg = (prices[0])
                stockGraphData.append({"x":json.dumps(date_js.isoformat()),"y":p_avg})

           # stockTableData = json.loads(stockTableData_obj.data)
            stockName = stockNames_dict[stock_code] + '({})'.format(stock_code)
            stockPrice = latest_price
            stockPriceChange_str = stockTableData[-1] # last value
            print(stockPriceChange_str)
            if stockPriceChange_str[0] == '+':
                stockPriceChange = float(stockPriceChange_str[1:])
            else:
                stockPriceChange = -float(stockPriceChange_str[1:])


            template = JINJA_ENVIRONMENT.get_template('templates/stock_data.html')
            template_values={"stockGraphData": json.dumps(stockGraphData),
                             "stockTableData": json.dumps(stockTableData),
                             "stockName": stockName,
                             "stockSymbol":stock_code,
                             "stockPrice": stockPrice,
                             "stockPriceChange": stockPriceChange}

            self.response.write(template.render(template_values))
        except IndexError:
            self.redirect('/')


class GetLatestPrice(webapp2.RequestHandler): # i think this is not used right
    def get(self):
        httplib.HTTPConnection._http_vsn = 10  # set up connection
        httplib.HTTPConnection._http_vsn_str = 'HTTP/1.0'

        #with open("stock_names.json", "r") as code_file:
        #   stock_codes = json.load(code_file)

        price_target_data = json.load(open("price_targets.json", "r"))
        price_url = "http://finance.yahoo.com/d/quotes.csv?s="
        for stock_code in sorted(stock_codes.keys()):  # get the url to get the earnings of the companies
            i = stock_codes[stock_code]  # to follow the variables of previous code
            if (i[-1].isdigit() or i[-2].isdigit() or '%' in i or '$' in i) or 'SEC' in i[
                                                                                        -3:]:  # all those with numbers at the back don't pay out dividends, either warrents, bonds or perpetual securities, later thinking of removing non-stocks from the stock list anyway
                continue
            yahoo_code = stock_code + ".SI" + "+"
            price_url += yahoo_code
        price_url = price_url[
                    :-1] + "&f=sl1ohgvbab6a5c1"  # [last price, open, high (day), low(day), volume(day), bid, ask, buyvol, sellvol]
        prices_dict = {}
        prices = urllib2.urlopen(price_url).readlines()
        for i in prices:
            curr_stock = i.decode("utf-8").strip().split(',')
            prices_dict[curr_stock[0][1:-4]] = curr_stock[1:]
        infile = open("stock_data_rui_en.json", "w")
        prices_dict = json.dumps(prices_dict)
        infile.write(prices_dict)
        infile.close()

class CheckAccept(webapp2.RequestHandler):  # method to check whether user accepts the T&C
    def post(self):
        user = users.get_current_user()
        resp = self.request.get("SubmitButton")
        print(resp)
        if resp == "Accept Legal":

            # create user
            p = Person()
            p.username = user.email()
            m = Msg(content=questions[0], from_user=False)
            p.chat_history = [m]  # the first thing should be the chat bot asking questions to the user
            p.spendings = {"Food and Drinks": 0,
                           "Entertainment": 0,
                           "Education": 0,
                           "Transport": 0,
                           "Others": 0}

            p.prev = questions[0]
            p.income = 1
            p.savings = 0
            p.q_index = 1
            p.put()

            time.sleep(1)
            self.redirect('/chatbot') # for profile analysing


class Budget(webapp2.RequestHandler):
    def get(self):
        # get user's spending and the datastore
        a = Average.query().fetch()
        self.response.write(a)


class Image(webapp2.RequestHandler):  # url to dynamically generates image using the image's key
    def get(self):
        # /image?image=URLSAFE_KEY
        image_key = ndb.Key(urlsafe=self.request.get('image'))  # pass in the image key
        img_obj = image_key.get()
        self.response.headers['Content-Type'] = 'image'
        self.response.out.write(img_obj.img)


class TestWrite(webapp2.RequestHandler):
    def get(self):
        if True:
            status = self.request.get('status')
            self.response.write(status)
        else:
            redirect = False
            t_query = TestClass.query().fetch()
            if t_query == []:

                t = TestClass()
            else:
                t = t_query[0]
            t.put()
            try:
                a = int(self.request.get("testparam"))
                redirect = True
            except:
                a = "Yo"
            self.response.write(a)
            print a
            if redirect:
                if a == 3:
                    self.redirect("/testwrite")
                elif a > 0:
                    self.redirect("/testwrite?testparam={}".format(a + 1))
                    print a


app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/pdpa',PDPA),
    ('/submitchat', SubmitChat),
    ('/checkaccept', CheckAccept),
    ('/testwrite', TestWrite),
    ('/image', Image),
    ('/budget', Budget),
    ('/chatbot',Chatbot),
    ('/savings',Savings),
    ('/goals', Goals),
    ('/investments',Investments),
    ('/stockData',StockData),
    ('/dividendCronJob', DividendCronJob),
    ('/priceTargetsCronJob', PriceTargetsCronJob),
    ('/reviewScoresCronJob',ReviewScoresCronJob),
    ('/analyseStocksCronJob',AnalyseStocksCronJob),
    ('/historicalPriceCronJob',HistoricalPriceCronJob)
#    ('/latestPriceCronJob',LatestPriceCronJob)
], debug=True)
