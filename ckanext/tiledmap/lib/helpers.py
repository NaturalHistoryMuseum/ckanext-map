#!/usr/bin/env python
# encoding: utf-8
#
# This file is part of ckanext-map
# Created by the Natural History Museum in London, UK

import re


# Template helpers
def mustache_wrapper(str):
    '''

    :param str: 

    '''
    return u'{{' + str + u'}}'


def dwc_field_title(field):
    '''Convert a DwC field name into a label - split on uppercase

    :param field: return: str label
    :returns: str label

    '''
    title = re.sub(u'([A-Z]+)', r' \1', field)
    title = title[0].upper() + title[1:]
    return title
