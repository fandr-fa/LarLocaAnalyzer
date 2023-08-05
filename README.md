Analyzer for localization data for Larian Games

*****
How to run the analyzer

- Open settings.json in a text editor and change "Perforce Folder" to the folder with your workspace.
- Launch the editor. This step is needed to updated the localization file.
- The script uses tqdm library. So, run "pip install tqdm" before running the script.
- Run the script
- Wait for the analyzer to finish. It will generate a file in format "loca_errors_report_[datetime].csv" in "results" folder.
- Open Google Sheets and File - Import - Upload to import the report. The report has columns:
    - handle;
    - word with an error;
    - suggestion - contains a possible correction for the word;
    - text - contains the actual text of the handle;

*****
How it works

The analyzer uses dictionary_en_small (taken from https://norvig.com/spell-correct.html) as its main dictionary plus all the dictionaries from folder "CustomDictionaries".
If the analyzer fails to find a word in dictionary_en_small it tries to find in dictionary_en_big (which is dump of page names of Wiktionary from https://dumps.wikimedia.org/).

Both small and big dictionaries must be present for it to work correctly. Folder with custom dictionaries could be empty.

The analyzer ignores all the handles from folder "ExcludedHandles". The folder can contain any number of .csv files, they need to store handles in the first column.
The analyzer ignores all the pairs "handle" + "word" from folder "CheckedHandlesAndWords". The folder can contain any number of .csv files, they need to store handles in the first column and words in the second, separated by a comma.
Both these folder can be empty.

The analyzer ignores handles if they contain 3 or more errors. Such cases are usually some arcane gibberish or goblins talking and mangling words.
The analyzer ignores words that it couldn't find in a dictionary, but that exist in at least three different lines in the localization file. This is done to prevent reporting fantasy words like coinpurse, for example.
The analyzer ignores all text between <i></i> tags because these tags are usually used for things like arcane incantations or drow/goblin/githyanki/etc specific languages.
All words starting with a capital letter are also ignored (to avoid reporting proper nouns).

The analyzer tries to make suggestions for corrections for the words it couldn't find using the algorithm and code described on https://norvig.com/spell-correct.html. The analyzer doesn't report words for which it doesn't have any suggestions to avoid dealing with too many false positives.

*****
How to deal with false positives

For handles - add them to excluded_handles.csv in "ExcludedHandles" folder or made a new file in that folder.
You can also import handles from the loca website. Use Search and then use button "Export results as CSV". Copy the downloaded file into "ExcludedHandles" folder.
By default the folder already contains several files imported from loca.

For combinations of handles & words you need to create a google sheet with two columns. First column - handles, second column - respective words. Then use
File - Download as CSV. Copy the downloaded file into "CheckedHandlesAndWords" folder.
Or make a column "False Positive" / "Addressed" in the google sheet in which you imported the report and the filter all false positives and save the result into a separate file, and move the file into "CheckedHandlesAndWords" folder.
