import datetime
import hashlib
import json
import re

# from geopy import Nominatim

from src.bstsouecepkg.extract import Extract
from src.bstsouecepkg.extract import GetPages


class Handler(Extract, GetPages):
    base_url = 'https://apps.nd.gov'
    NICK_NAME = 'apps.nd.gov'
    fields = ['overview', 'documents']

    header = {
        'User-Agent':
            'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Mobile Safari/537.36',
        'Accept':
            'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'accept-language': 'en-US,en;q=0.9,ru-RU;q=0.8,ru;q=0.7'
    }

    def get_by_xpath(self, tree, xpath, return_list=False):
        try:
            el = tree.xpath(xpath)
        except Exception as e:
            print(e)
            return None
        if el:
            if return_list:
                return [i.strip() for i in el]
            else:
                return el[0].strip()
        else:
            return None
    def reformat_date(self, date, format):
        date = datetime.datetime.strptime(date.strip(), format).strftime('%Y-%M-%d')

        return date

    def check_tree(self, tree):
        print(tree.xpath('//text()'))

    def check_create(self, tree, xpath, title, dictionary, date_format=None):
        item = self.get_by_xpath(tree, xpath)
        if item:
            if date_format:
                item = self.reformat_date(item, date_format)
            dictionary[title] = item.strip()
    def get_address(self, tree):
        addr = self.get_by_xpath(tree, '//div[@class="address"]//span/text()', return_list=True)
        if not addr:
            return None
        fullAd = ' '.join(addr[:-1])
        temp = {
            'fullAddress': fullAd + ', United States',
            'country': 'United States'
        }
        try:
            zip = re.findall('PO BOX \d+', fullAd)[0]
        except:
            zip = None
        if zip:
            zip = zip.split('PO BOX ')[-1]
            temp['zip'] = zip
        street = None
        city = None
        if len(addr) == 4:
            street = addr[0]
            city = addr[2].split(',')[0]
        if len(addr) == 3:
            street = addr[0]
            city = addr[1].split(',')[0]
            if zip:
                city = addr[2].split(',')[0]

        if street:
            temp['streetAddress'] = street
        if city:
            temp['city'] = city
        return temp
    def get_agent(self, tree, addr1):
        addr = dict(addr1)
        addr['@type'] = 'individual'
        name = self.get_by_xpath(tree, '//div[@class="address"]//span/strong/text()')
        if name:
            addr['name'] = self.get_by_xpath(tree, '//div[@class="address"]//span/strong/text()')
            return addr
        else:
            return None



    def getpages(self, searchquery):
        url = 'https://apps.nd.gov/sc/busnsrch/busnSearch.htm'
        tree = self.get_tree(
            url,
            headers=self.header)

        data = {
            'srchName': searchquery,
            'srchSystemId': '',
            'srchType': 'And',
            'resultsPerPage': '25',
            'srchOwnerName': '',
            'srchLicenseNo': '',
            'srchCity': '',
            'srchCounty': '',
            'command': 'Search',
        }
        tree = self.get_tree(url, headers=self.header, data=data, method='POST')
        dat = self.get_by_xpath(tree, '//tr/td[3]/a/@href', return_list=True)
        names = self.get_by_xpath(tree, '//tr/td[1]/text()', return_list=True)
        dat = [re.findall("'[\w\s]+'",i)[1:] for i in dat]
        res_list = []
        for i, name in zip(dat, names):
            if name == '':
                continue
            temp = [h[1:-1] for h in i]
            res_list.append('?='.join(temp))

        return res_list

    def get_overview(self, link_name):
        #print(link_name)
        comp_id = link_name.split('?=')[0]
        tr_name = link_name.split('?=')[-1]

        data = {
            'submitType': 'submitDetail',
            'submitID': comp_id,
            'submitEntityType': tr_name,
        }
        #print(data)
        url = 'https://apps.nd.gov/sc/busnsrch/busnSearch.htm'
        tree = self.get_tree(url, data=data, headers=self.header, method='POST')


        company = {}


        try:
                orga_name = self.get_by_xpath(tree, '//h3/text()')
        except:
            return None

        if orga_name: company['vcard:organization-name'] = orga_name.strip()

        company['isDomiciledIn'] = 'US'
        self.check_create(tree,'//table[@summary="Entity details"]//tr//td//strong//text()[contains(.,"Status")]/../following-sibling::text()','hasActivityStatus', company)
        self.check_create(tree,'//table[@summary="Entity details"]//tr//td//strong//text()[contains(.,"State of Origin:")]/../following-sibling::text()','registeredIn', company)
        self.check_create(tree,'//table[@summary="Entity details"]//tr//td//strong//text()[contains(.,"Phone:")]/../following-sibling::text()','tr-org:hasRegisteredPhoneNumber', company)
        #date_org = self.get_by_xpath(tree, '//table[@summary="Entity details"]//tr//td//strong//text()[contains(.,"Original File Date:")]/../following-sibling::text()', )
        self.check_create(tree,'//table[@summary="Entity details"]//tr//td//strong//text()[contains(.,"Original File Date:")]/../following-sibling::text()','hasLatestOrganizationFoundedDate:', company, date_format='%d/%M/%Y')
        #self.check_create(tree,'//table[@summary="Entity details"]//tr//td//strong//text()[contains(.,"Type")]/../following-sibling::text()','hasActivityStatus', company[''])
        lei = self.get_by_xpath(tree, '//table[@summary="Entity details"]//tr//td//strong//text()[contains(.,"Type")]/../following-sibling::text()')

        if lei:
            company['lei:legalForm']= {
                'code':'',
                'label':lei
            }
        company['identifiers'] = {
            'other_company_id_number': comp_id
        }
        addr = self.get_address(tree)
        if addr:
            company['mdaas:RegisteredAddress'] = addr
        serv = self.get_by_xpath(tree, '//h4/text()[contains(., "Nature of Business")]/../following-sibling::div/text()')
        if serv:
            company['Service'] = {
                'serviceType': serv
            }
        shares_class = self.get_by_xpath(tree, '//h4/text()[contains(., "Authorized Shares")]/../following-sibling::div//tr/td[1]/text()')
        shares_count = self.get_by_xpath(tree,
                                         '//h4/text()[contains(., "Authorized Shares")]/../following-sibling::div//tr/td[2]/text()')

        if shares_class and shares_count:
            company['classOfShares'] = {
                'class': shares_class,
                'count':shares_count
            }

        if addr:
            agent = self.get_agent(tree, addr)
            if agent:
                company['agent'] = agent
        company['@source-id'] = self.NICK_NAME
        #print(company)
        return company

    def get_documents(self, link_name):
        comp_id = link_name.split('?=')[0]
        tr_name = link_name.split('?=')[-1]

        data = {
            'submitType': 'submitDetail',
            'submitID': {comp_id},
            'submitEntityType': {tr_name},
        }
        url = 'https://apps.nd.gov/sc/busnsrch/busnSearch.htm'
        tree = self.get_tree(url, data=data, headers=self.header, method='POST')
        docs = []
        doci = self.get_by_xpath(tree, '//h4/text()[contains(., "Generate an Annual Report To File")]/../following-sibling::div/a/@onclick', return_list=True)
        doci = [i.split('("')[-1] for i in doci]
        doci = [i.split('")')[0] for i in doci]
        years = [i.split('year=')[-1] for i in doci]
        years = [i.split('&')[0] for i in years]
        for doc, year in zip(doci, years):
            temp = {
                'date': year,
                'description': 'Annual Report',
                'url': self.base_url +'/sc/busnsrch/' +doc
            }
            docs.append(temp)

        return docs
        # print(links)
