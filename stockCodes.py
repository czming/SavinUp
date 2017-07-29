import urllib2
import json                 #use http://infopub.sgx.com/Apps?A=COW_App_DB&B=isincodedownload&F=1 to find stock codes
                            #when comparing the company, may want to capitalize since I've noticed that this data is not the same capitalization as the SGX one


def get_stock_codes():
    fileobj = urllib2.urlopen("http://infopub.sgx.com/Apps?A=COW_App_DB&B=isincodedownload&F=1").readlines()
    fileobj = fileobj[1:]
    code_dict = {}
    # infile = open("short_stock_codes.json", "w")
    for i in range(len(fileobj)):
        fileobj[i] = fileobj[i].decode("utf-8")
        fileobj[i] = fileobj[i].split('  ')
        j = 0
        while j < len(fileobj[i]):
            if fileobj[i][j] == '':
                del fileobj[i][j]
                continue
            fileobj[i][j] = fileobj[i][j].strip()
            j += 1
    for i in fileobj:
        if len(i[2]) < 5:           #want to remove those with abnormaly long codes (based on previous data runs they don't have dividends or price anyway)
            code_dict[i[3]] = i[2]
    # infile.write(json.dumps(code_dict))
    # print(len(code_dict))
    # infile.close()
    return code_dict


def get_stock_names():
    fileobj = urllib2.urlopen("http://infopub.sgx.com/Apps?A=COW_App_DB&B=isincodedownload&F=1").readlines()
    fileobj = fileobj[1:]
    code_dict = {}              #reset code_dict
    # infile = open("short_stock_names.json", "w")
    for i in range(len(fileobj)):
        fileobj[i] = fileobj[i].decode("utf-8")
        fileobj[i] = fileobj[i].split('  ')
        j = 0
        while j < len(fileobj[i]):
            if fileobj[i][j] == '':
                del fileobj[i][j]
                continue
            fileobj[i][j] = fileobj[i][j].strip()
            j += 1
    for i in fileobj:
        if len(i[2]) < 5:           #want to remove those with abnormaly long codes (based on previous data runs they don't have dividends or price anyway)
            code_dict[i[2]] = i[3]
    # infile.write(json.dumps(code_dict))
    # print(len(code_dict))
    # infile.close()
    return code_dict
