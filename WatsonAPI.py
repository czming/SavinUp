import requests
import requests_toolbelt.adapters.appengine
import json

# Use the App Engine Requests adapter. This makes sure that Requests uses
# URLFetch.
requests_toolbelt.adapters.appengine.monkeypatch()
data = json.load(open("conf.json",'r')) # read username and password from conf.json which which will be under gitignore

conf = {
  "url": "https://gateway.watsonplatform.net/natural-language-understanding/api",
  "username": data["username"],
  "password": data["password"]
}


text = "I went for a Transformers movie. It costs $50"
features = "categories,entities"

cat_map = {"food and drink":"Food and Drinks",
            "art and entertainment":"Entertainment",
            "education":"Education",
            "transport":"Transport",
            "transports":"Transport",
            "travel":"Transport"
               }
#keywords are the items that the user buys
#entities refer to the cost of the items
#categories refer to the category that the keywords are in
def chatbot(text): # do i actually need this since I have chatbot2 already
    url = "https://gateway.watsonplatform.net/natural-language-understanding/api/v1/analyze?version=2017-02-27&text={0}.&features={1}".format(text,features)
    r = requests.get(url, auth=(conf["username"], conf["password"]))
    print(r.text)
    try:
        return r.json()["error"]
    except:
        pass
    try:
        categories = r.json()["categories"]
    except:
        categories = []
    try:
        entities = r.json()["entities"]
    except:
        entities = []
    #keywords = r.json()["keywords"]
    uniqueCats = []
    for c in categories: #to remove duplicated categories
        if c['label'].split('/')[1] in uniqueCats:
            continue
        uniqueCats.append(c['label'].split('/')[1])

    costs = [e["text"] for e in entities] #do note that it can include person entities also
    outText = ""
    if len(costs) > len(uniqueCats): #e.g. person spends $40 and $60 on lunch and dinner but both belongs to one cat
        for cost in costs:
            outText += "{},{}\n".format(uniqueCats[0],cost)
    else:
        for i in range(len(costs)):
            if costs[i][0] == "$":
                outText += "{},{}\n".format(uniqueCats[i],costs[i])

    return outText




def chatbot2(text): # buying one thing only
    features = "categories,entities"
    url = "https://gateway.watsonplatform.net/natural-language-understanding/api/v1/analyze?version=2017-02-27&text={0}.&features={1}".format(
        text, features)
    if "$" not in text: #do not even need to process this
        return {}
    if "save" in text.lower() or "add" in text.lower():
        return add_savings(text) # returns {save:value} as defined below
        # the user might want to spends and save at the same tie
    r = requests.get(url, auth=(conf["username"], conf["password"]))
    print(r.text)
    if "error" in r.json():
        return chatbot2(add_on(text))
    try:
        categories = r.json()["categories"]
    except:
        categories = []
    try:
        entities = r.json()["entities"] #cost of the product
    except:
        entities = []
    # keywords = r.json()["keywords"]
    cost = 0
    for c in entities:
        if c["text"][0] == '$':
            cost = float(c["text"].replace('$',''))
            break

    MULTIPLIER = 1 # when user types something like 6 oranges for $0.30 each

    text_array = text.split(' ')
    if 'each' in text_array:
        for word in text_array:
            try:
                MULTIPLIER = int(word)
                break
            except:
                pass
    cost = cost*MULTIPLIER


    try:
        category_cost =  {cat_map[categories[0]['label'].split('/')[1]]: cost}

    except: # KeyError or no cat
        category_cost = {"Others": cost} # when category is not recognised

    return category_cost

def get_category(text):
    url = "https://gateway.watsonplatform.net/natural-language-understanding/api/v1/analyze?version=2017-02-27&text={0}.&features={1}".format(
        text, "categories")
    r = requests.get(url, auth=(conf["username"], conf["password"]))

    try:
        categories = r.json()["categories"]
    except:
        categories = []
    category = "Others"
    for cat in categories:
        if cat["label"].split('/')[1] in cat_map: # if there is a recognised category
            return cat_map[cat["label"].split('/')[1]]
    return category


def add_on(text):
    return "I bought " + text


def merge_dict(dict1, dict2): # merges two dictionaries tgt to give a new dictionary value
    for k in dict2:
        if k in dict1:
            dict1[k] = dict1[k] + dict2[k]
        else:
            dict1[k] = dict2[k]
    return dict1

def separate(text): # used to separate the number of items that the user enters
    # eg. I bought eggs for $50, bananas for $90 and oranges for $80
    replacings = [',', 'and ']
    for r in replacings:
        text = text.replace(r, ';')
    text_array = [t for t in text.split(';') if '$' in t]

    return text_array # for multiple API calls


def add_savings(text): # execute this function when you need to save
    value = 0
    for word in text.split():
        if word[0] == '$':
            print(word)
            value = float(word.replace('$', ''))
            break

    return {"save":value}

def risk_assessment(text):
    features = "emotion" # tone of the user is tied to their risk factor
    url = "https://gateway.watsonplatform.net/natural-language-understanding/api/v1/analyze?version=2017-02-27&text={0}.&features={1}".format(
        text, features)
    r = requests.get(url, auth=(conf["username"], conf["password"]))
    if "error" in r.json():
        pass # return something

    emotions = r.json()["emotion"]["document"]["emotion"]
    # anger joy sadness fear disgust



    # outfile = open("logs.txt",'a')
# outfile.write(text)
# outfile.write('\n')
# outfile.write(outText)
# outfile.close()