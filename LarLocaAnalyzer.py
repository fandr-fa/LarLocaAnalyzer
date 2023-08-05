from datetime import datetime
import xml.etree.cElementTree as ElementTree
import json
import os
import os.path
import re
import csv
from tqdm import tqdm
import time

from collections import Counter

def words_from_text(text):
    return re.findall(r'\w+', text.lower())

def read_custom_dictionaries():

    words = []

    folder = os. getcwd() + "\\CustomDictionaries"
    if not os.path.exists(folder):
        return words

    for filename in os.listdir(folder):
        if filename.endswith(".txt"):
            with open(os.path.join(folder, filename), 'r', encoding='utf-8') as file:
                content = file.read()
                words.extend(words + words_from_text(content))

    return words

# Combine the default dictionary with all the custom dictionaries defined for the project
def build_project_dictionary():

    dictionary_big = words_from_text(open('dictionary_en_big.txt', encoding='utf-8').read())

    dictionary_small = words_from_text(open('dictionary_en_small.txt', encoding='utf-8').read())

    custom_dictionaries = read_custom_dictionaries()

    dictionary_big.extend(custom_dictionaries)
    dictionary_big.extend(dictionary_small)

    return dictionary_big

WORDS = Counter(words_from_text(open('dictionary_en_small.txt').read()))

DICTIONARY_BIG = build_project_dictionary()

FULL_LOCALIZATION_DATA = {}

# if we got a suggestion for an incorrect word, we save it
# to avoid looking for suggestions for the same word again
SUGGESTIONS_CACHE = {}

# if we checked the word and it is correct we save it
# to avoid doing all the checks again for the same word
CORRECT_WORDS_CACHE = []

# only handles, when we need to completely ignore the whole phrase, mostly for system info etc
EXCLUDED_HANDLES = []

# combinations of handles and words, because for one NPC a word could be a mistake, for another (drunk person) - not
EXCLUDED_HANDLES_AND_WORDS = {}

# cache of incorrect words - for every incorrect word we store all the lines that use that word
INCORRECT_WORDS_CACHE = {}

# settings
SETTINGS = {}

LOCA_LINK = "https://loca.larian.network/BG3/strings/"

def P(word, N=sum(WORDS.values())):
    "Probability of `word`."
    return WORDS[word] / N

def correction(word):
    "Most probable spelling correction for word."
    return max(candidates(word), key=P)

def correction2(word):
    "Most probable spelling correction for word."
    return max(candidates2(word), key=P)

def candidates(word):
    "Generate possible spelling corrections for word."
    return (known([word]) or known(edits1(word)) or [word])

def candidates2(word):
    "Generate possible spelling corrections for word."
    return (known([word]) or known(edits1(word)) or known(edits2(word)) or [word])

def known(words):
    "The subset of `words` that appear in the dictionary of WORDS."
    return set(w for w in words if w in WORDS)

def known_big(words):
    "The subset of `words` that appear in the dictionary of WORDS."
    return set(w for w in words if w in DICTIONARY_BIG)

def edits1(word):
    "All edits that are one edit away from `word`."
    letters    = 'abcdefghijklmnopqrstuvwxyz'
    splits     = [(word[:i], word[i:])    for i in range(len(word) + 1)]
    deletes    = [L + R[1:]               for L, R in splits if R]
    transposes = [L + R[1] + R[0] + R[2:] for L, R in splits if len(R)>1]
    replaces   = [L + c + R[1:]           for L, R in splits if R for c in letters]
    inserts    = [L + c + R               for L, R in splits for c in letters]
    return set(deletes + transposes + replaces + inserts)

def edits2(word):
    "All edits that are two edits away from `word`."
    return (e2 for e1 in edits1(word) for e2 in edits1(e1))

def read_settings():

    with open("settings.json") as json_file:
        data = json.load(json_file)

        SETTINGS['perforce_folder'] = data['perforce_folder'].rstrip('/')
        SETTINGS['localization'] = SETTINGS['perforce_folder'] + '/Stable/LSProjects/Apps/Gustav/Data/Localization/English/english.xml'
        SETTINGS['dictionary_big'] = data['dictionary_big']
        SETTINGS['dictionary_small'] = data['dictionary_small']

def extract_handle(line):
    if line.find("handle") != -1:
        slice_object = slice(12, 49)
        handle = line.strip()[slice_object]
        return handle
    else:
        return ""

def prepare_excluded_handles():

    folder = os. getcwd() + "\\excludedHandles"
    if not os.path.exists(folder):
        return []

    for filename in os.listdir(folder):
        if filename.endswith(".csv"):
            with open(os.path.join(folder, filename), 'r') as file:
                reader = csv.reader(file)
                for row in reader:
                    handle = row[0]
                    if handle == "StringHandle":
                        continue
                    EXCLUDED_HANDLES.append(handle)
    return EXCLUDED_HANDLES

def prepare_excluded_handles_and_words():

    folder = os. getcwd() + "\\checkedHandlesAndWords"
    if not os.path.exists(folder):
        return {}

    for filename in os.listdir(folder):
        if filename.endswith(".csv"):
            with open(os.path.join(folder, filename), 'r', encoding='utf-8') as file:
                reader = csv.reader(file, delimiter=',')
                for row in reader:
                    if len(row) < 2:
                        print(row)
                        continue
                    handle = row[0]
                    word = row[1]
                    if not handle in EXCLUDED_HANDLES_AND_WORDS:
                        EXCLUDED_HANDLES_AND_WORDS[handle] = []
                    EXCLUDED_HANDLES_AND_WORDS[handle].append(word)

    return EXCLUDED_HANDLES_AND_WORDS

def remove_images(text):
    return re.sub(r'<LSTag.*?Image.*?>.*?</LSTag>|<LSTag.*?Image.*?/>', '', text)

def remove_html_tags(text):
    text = text.replace('&lt;br&gt;', ' ') \
        .replace("&lt;b&gt;", ' ') \
        .replace("&lt;/b&gt;", ' ')\
        .replace('&lt;i&gt;', ' ') \
        .replace('&lt;//i&gt;', ' ') \
        .replace('&lt;/i&gt;', ' ') \
        .replace('&lt;', '') \
        .replace('&gt;', '') \
        .replace('<b>', '') \
        .replace('</b>', '') \
        .replace('<br>', ' ') \
        .replace('<Br>', ' ') \
        .replace('</br>', '') \
        .replace('<hl>', '') \
        .replace('</hl>', '') \
        .replace('<h1>', '') \
        .replace('</h1>', '') \
        .replace('&br;', '') \
        .replace('//i;', '') \
        .replace("<i>", '') \
        .replace("</i>", '')
    return text

def remove_contractions(text):

    stripped_words = []
    words = text.split()
    for word in words:
        stripped_word = word.strip("'")
        stripped_word = stripped_word.strip('"')
        stripped_words.append(stripped_word)
    text = ' '.join(stripped_words)

    return text.replace("'s", '')\
        .replace("'d", '') \
        .replace("'m", '') \
        .replace("'ve", '')\
        .replace("'ll", '')\
        .replace("'re", '')\
        .replace("'", '')

def remove_punctuation(text):
    return text .replace('*', '')\
        .replace(' - ', ' ')\
        .replace('"', '') \
        .replace('_', ' ') \
        .replace('...', ' ') \
        .replace('.', '') \
        .replace(',', '')\
        .replace(';', '') \
        .replace(':', '') \
        .replace('!', '') \
        .replace('?', '')\
        .replace('%', '') \
        .replace('(', '') \
        .replace(')', '') \
        .replace('<', '') \
        .replace('>', '') \
        .replace('[', '') \
        .replace("\\", ' ') \
        .replace('/', ' ') \
        .replace(']', '')

# doesn't remove '<', '/' and '>' to prevent loosing <i> tags
# which are important later
def remove_punctuation_basic(text):
    return text .replace('*', '')\
        .replace(' - ', ' ')\
        .replace('"', '') \
        .replace('_', ' ') \
        .replace('...', ' ') \
        .replace('.', '') \
        .replace(',', '')\
        .replace(';', '') \
        .replace(':', '') \
        .replace('!', '') \
        .replace('?', '')\
        .replace('%', '') \
        .replace('(', '') \
        .replace(')', '') \
        .replace('[', '') \
        .replace("\\", ' ') \
        .replace(']', '')

def remove_string_versions(text):
    return text.replace('v1', '')\
        .replace('v2', '')\
        .replace('v3', '')

def has_numbers(input_string):
    return any(char.isdigit() for char in input_string)

def remove_ls_tags(text):
    return re.sub(r'<LSTag.*?>(.*?)</LSTag>', r'\1', text)

def remove_square_brackets(text):
    return re.sub(r'\[.*?\]', '', text)

def check_only_this_word_within_tags(word, text):

    text = remove_punctuation_basic(text)
    text = text.strip()

    start_tag = "<i>"
    end_tag = "</i>"
    start_index = text.find(start_tag)
    end_index = text.find(end_tag)

    if start_index == -1 or end_index == -1 or end_index <= start_index:
        return False

    contained_text = text[start_index + len(start_tag) : end_index].strip()
    contained_words = contained_text.split(" ")

    if len(contained_words) != 1:
        return False

    if contained_words[0] == word:
        return True

    return False

def clean_data(text, handle):

    text = text.strip()

    text = remove_images(text)

    text = remove_ls_tags(text)

    text = remove_square_brackets(text)

    text = remove_html_tags(text)

    text = remove_string_versions(text)

    # text = remove_contractions(text)  # contractions must be removed before removing punctuation!

    text = remove_punctuation(text)

    return text

def parse_localization():

    tree = ElementTree.parse(SETTINGS['localization'])
    root = tree.getroot()
    stripped_data = {}

    for i in tqdm(range(len(root))):

        child = root[i]
        if child.text is None:
            continue
        if child.text.find('|') != -1 or child.text == "_":
            continue
        handle = child.attrib['contentuid']

        if handle in EXCLUDED_HANDLES:
            continue

        if handle not in FULL_LOCALIZATION_DATA:
            FULL_LOCALIZATION_DATA[handle] = ""
        FULL_LOCALIZATION_DATA[handle] = child.text

        text = clean_data(child.text, handle)

        if handle not in stripped_data:
            stripped_data[handle] = ""
        stripped_data[handle] = text

    return stripped_data

def load_english_dictionary():
    with open(SETTINGS['dictionary_big'], encoding='utf-8') as word_file:
        valid_words = set(word_file.read().split())

    return valid_words

def has_no_error(word, text, english_dictionary, first_word):

    # ignore words with spec symbols
    if word.find("-") != -1 \
        or word.find("—") != -1 \
        or word.find("$") != -1 \
        or word.find("#") != -1 \
        or word.find("@") != -1 \
        or word.find("'") != -1:
        return True

    # ignore one-letter words
    if len(word) == 1:
        return True

    # ignore words with numbers
    if has_numbers(word):
        return True

    # # ignore Proper Nouns
    if word[0].isupper() and len(word) > 1:
       return True

    word = word.lower()

    # ignore if in the small dictionary
    if word in english_dictionary:
        return True

    # ignore words within <i> </i> tags
    # these are unique words, spell incantations etc

    # ignore plurals
    if word[-1] == 's' and word[:-1] in english_dictionary:
        return True

    if word[-1] == 'f' and (word[:-1] + "ves") in english_dictionary:
        return True

    # ignore contractions like "singin"
    if word[-1] == 'n' and (word + 'g') in english_dictionary:
        return True

    # ignore past tense / would contractions
    if word[-1] == 'd' and word[:-1] in english_dictionary:
        return True

    # ignore words like "Aaargh!"
    if has_sequence_of_three_same_letters(word):
        return True

    # ignore if in the big dictionary
    # this should take care of most of the cases
    # like gerunds etc
    if word in DICTIONARY_BIG:
       return True

    # ignore plurals in big dictionary
    if word[-1] == 's' and word[:-1] in DICTIONARY_BIG:
        return True

    if word[-1] == 'f' and (word[:-1] + "ves") in DICTIONARY_BIG:
        return True

    return False

def extract_errors(stripped_data):

    english_dictionary = load_english_dictionary()

    errors = {}

    for handle, line in tqdm(stripped_data.items()):

        words = line.split()
        for word in words:

            if word in CORRECT_WORDS_CACHE:
                continue

            if word in INCORRECT_WORDS_CACHE:
                INCORRECT_WORDS_CACHE[word].add(line)
                if handle not in errors:
                    errors[handle] = [word]
                else:
                    errors[handle].append(word)
                continue

            if has_no_error(word, line, english_dictionary, word == words[0]):
                CORRECT_WORDS_CACHE.append(word)
                continue
            else:
                INCORRECT_WORDS_CACHE[word] = set()
                INCORRECT_WORDS_CACHE[word].add(line)
                if handle not in errors:
                    errors[handle] = [word]
                else:
                    errors[handle].append(word)

    return errors

# text in italic tags is usually some arcane incantation (= gibberish)
# or unique words of goblins / githyanki / drow etc
# we should ignore the text in italic tags otherwise we get too many
# false positives
def word_in_italic_tags(word, text):

    # multiple tags within one string
    startIndex = text.find("<i>")
    endIndex = text.rfind("</i>")
    wordIndex = text.find(word)

    if startIndex == -1 or endIndex == -1 or wordIndex == -1:
        return False
    else:
        if wordIndex >= startIndex and wordIndex <= endIndex:
            return True
        else:
            return False

# American Dictionary is used
# "prioritise" will be considered a mistake and "prioritize" will be suggested
# we need to ignore such cases since we used British English
def is_british_spelling(word1, word2):
    if len(word1) != len(word2):
        return False

    index = -1
    for i in range(len(word1)):
        if word1[i] != word2[i]:
            if index != -1:
                return False
            index = i

    if index == -1 or word1[index] != 's' or word2[index] != 'z':
        return False

    return True

# if there is an Upper letter in the word, but it's not the first letter
# then there is a missing space somewhere
# we don't need words that don't have any lower case letters at all
def has_uppercase_letter_in_middle(word):
    if has_lowercase_letter(word):
        for i in range(1, len(word)):
            if word[i].isupper():
                return True
    return False

def has_lowercase_letter(word):
    for letter in word:
        if letter.islower():
            return True
    return False

# ignore stuff like "Aaaaa!"
def has_sequence_of_three_same_letters(word):
    for i in range(len(word) - 2):
        if word[i] == word[i+1] == word[i+2]:
            return True
    return False

def write_errors(errors):

    folderName = "results"
    if not os.path.exists(folderName):
        os.mkdir(folderName)

    currentDate = datetime.today().strftime('%d_%m_%Y_%H_%M_%S')

    fileName = "loca_errors_report" + "_" + currentDate + ".csv"

    file = os.path.join(folderName, fileName)

    with open(file, 'w', encoding='utf-8') as f_errors:

        for handle, words in tqdm(errors.items()):

            if handle in EXCLUDED_HANDLES:
                continue

            # if the text of the handle contains 3 errors or more - ignore it
            # most likely some giberrish
            if len(words) >= 3:
                continue

            for word in words:

                try:
                    if handle in EXCLUDED_HANDLES_AND_WORDS and word in EXCLUDED_HANDLES_AND_WORDS[handle]:
                        continue
                except:
                    print("An exception occurred with handle " + handle + " and word " + word)

                if has_uppercase_letter_in_middle(word):
                    f_errors.write(LOCA_LINK + handle + ';' + handle + ';' + word + ';' + "missing space between two words" + ';' + FULL_LOCALIZATION_DATA[handle] + '\n')

                # if we encountered the incorrect word in 3 or more different lines
                # we don't report it - most likely a fantasy word
                # this is different from the check above - this check is for words
                # the check above is for phrases (handles)
                if word in INCORRECT_WORDS_CACHE and len(INCORRECT_WORDS_CACHE[word]) >= 3:
                    continue

                if word_in_italic_tags(word, FULL_LOCALIZATION_DATA[handle]):
                    continue

                if word in SUGGESTIONS_CACHE:
                    suggestion = SUGGESTIONS_CACHE[word]
                else:
                    correctedWordSuggestion = correction(word)
                    if not correctedWordSuggestion and len(word) > 0 and word[-1] == "s":
                        correctedWordSuggestion = correction(word[:-1])

                suggestion = correctedWordSuggestion if correctedWordSuggestion != word else ""
                if suggestion == "":
                    correctedWordSuggestion = correction2(word)
                    suggestion = correctedWordSuggestion if correctedWordSuggestion != word else ""

                if suggestion == "":
                    continue

                cleanedData = FULL_LOCALIZATION_DATA[handle].replace('\n', '')

                if not is_british_spelling(word, suggestion):
                    f_errors.write(LOCA_LINK + handle + ';' + handle + ';' + word + ';' + suggestion + ';' + cleanedData + '\n')
        print("Report saved into file " + file)

def all_files_exist():

    if not os.path.exists(SETTINGS["localization"]):
        print("Couldn't find localization file " + SETTINGS["localization"])
        print("Make sure you updated the Perforce Folder in settings.json")
        return False

    if not os.path.exists(SETTINGS["dictionary_big"]):
        print("Couldn't find the file with the big dictionary")
        return False

    if not os.path.exists(SETTINGS["dictionary_small"]):
        print("Couldn't find the file with the small dictionary")
        return False

    return True

if __name__ == '__main__':

    print("Analysis started.")

    try:
        read_settings()
    except:
        print("An exception occurred while reading the settings. The analysis is aborted.")
        print("Press any key to close the window.")
        readKey = input()
        exit()

    # check if all the needed files are present
    # otherwise abort the program
    if not all_files_exist():
        print("Some of the critical files missing. The analysis is aborted. Check and update the settings.json file.")
        print("Press any key to close the window.")
        readKey = input()
        exit()

    print("Reading excluded handles and words ... ")
    EXCLUDED_HANDLES = prepare_excluded_handles()
    EXCLUDED_HANDLES_AND_WORDS = prepare_excluded_handles_and_words()
    print("Done.")

    print("Reading false positives ... ")
    EXCLUDED_HANDLES_AND_WORDS = prepare_excluded_handles_and_words()
    print("Done.")

    print("Parsing the localization file ... ")
    stripped_data = parse_localization()
    print("Done.")

    print("Searching for words that aren't in the dictionary ... ")
    errors = extract_errors(stripped_data)
    print("Done.")

    print("Looking for corrections, removing false positives and reporting errors ... ")
    write_errors(errors)
    print("Done.")

    print("Analysis finished.")
    print("Press any key to close the window.")

    readKey = input()
