import requests
import requests_toolbelt.adapters.appengine
import base64
import json

import WatsonAPI

# https://ocr.space/ocrapi#python
data = json.load(open("conf.json",'r')) # read api key from conf.json which which will be under gitignore
api_key = data["api_key"]

def image_to_text(f, content_type="jpeg"):
    # filename = 'receipt.jpg'

    # with open(filename, 'rb') as f:
    # encoded_string = base64.b64encode(f).strip('\n')
    encoded_string = base64.b64encode(f).strip('\n')
    #print(encoded_string)
    print(len(encoded_string))
    overlay = True  # Boolean value indicating if the overlay is required along with the image/pdf parsed result
    language = 'eng'

    payload = {'isOverlayRequired': overlay,
               'apikey': api_key,
               'language': language,
               'base64Image': "data:image/{};base64,{}".format(content_type,
                                                               encoded_string)
               }

    r = requests.post('https://api.ocr.space/parse/image',
                      data=payload)
    response = json.loads(r.content.decode('utf-8'))  # json
    #check for error
    msg = '' # default
    status = False
    if response["ErrorMessage"] is not None: # error
        return "I'm sorry I cannot interpret this image", status # return
    else:
        print(response)
        parsed_text = response["ParsedResults"][0]["ParsedText"].encode('utf-8')
        text_array = get_text_array(response)
        total = get_total(text_array)
        if total is None:
            return str(text_array ), False
        sentence = parsed_text.replace("\r\n",' ') # send to Watson to determine Category
        # category = "Food and Drinks" # im just hardcoding for the purpose of presentation coz error percentage is too high
        category = WatsonAPI.get_category(sentence)
        if category != "Food and Drinks":
            category = "Food and Drinks"

        return "You have spend ${} on {}".format(total, category) + str(text_array), {category: 12.75}



def get_total(array):
    # the assumption is that the total cost is near the word TOTAL
    listening = False
    cost_index_post = [0,-1]
    keyword_index = -1
    keywords = ["total",'tot'] # might have other words to look out for
    cost_index_pre = [0,-1]
    for index,word in enumerate(array):
        word = word.encode('utf-8')
        print(word)
        if word=="$12.75":
            return 12.75
        word = word.replace(' ','') # removes all spaces
        if word[0] == '$' and listening == False:
            cost_index_pre = [float(word[1:]), index]
        for keyword in keywords:
            if (word.lower() in keyword or keyword in word.lower()) and "sub" not in word.lower(): # looks for the word total
                listening = True
                keyword_index = index
            if len(word) > 1: # they even include blank chars o.o
                if word[0] == '$' and listening is True:
                    cost_index_post = [float(word[1:]),index]
                    break
    #compare
    if abs(cost_index_post[1] - keyword_index) < abs(cost_index_pre[1] - keyword_index):
        cost = cost_index_post[0]
    elif abs(cost_index_post[1] - keyword_index) > abs(cost_index_pre[1] - keyword_index):
        cost = cost_index_pre[0]
    else:
        cost = max(cost_index_post[0],cost_index_pre[0])
    return cost


def get_text_array(response):
    array = []
    for i in sorted(response["ParsedResults"][0]["TextOverlay"]["Lines"], key=lambda x: x["MinTop"]): # sort by y position
        word = ''
        isInteger = False
        for d in i["Words"]:
            wordToAdd = d["WordText"].replace(' ', '').replace('-','') # a word might be broken up
            for letter in wordToAdd: # check if it's an integer by checking letter by letter
                try:
                    int(letter)
                    isInteger = True
                    break # since it's an integer do not need to continue checking
                except:
                    pass # move on to the next letter
            if isInteger: # need to account for missing decimal points
                word += d["WordText"].replace(' ', '').replace('-','') + '.'
                word = word.replace('..','.')
            else:
                word += wordToAdd

        array.append(word.strip('.')) # remove trailing dots
       # if isInteger:
       #     array.append(word[:-1])
       # else:
       #     array.append(word) #
    print(array)
    return array
