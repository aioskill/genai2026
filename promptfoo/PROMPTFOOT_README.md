Using the assert property, we can check if the model’s answer contains the expected answer. 
This is the list of all the available assertions:

equals: output matches exactly
contains: output contains substring
icontains: output contains substring, case insensitive
regex: output matches regex
starts-with: output starts with string
contains-any: output contains any of the listed substrings
contains-all: output contains all of the listed substrings
is-json: output is valid json (optional json schema validation)
contains-json: output contains valid json (optional json schema validation)
javascript: provided Javascript function validates the output
python: provided Python function validates the output
webhook: provided webhook returns
similar: embeddings and cosine similarity are above a threshold
llm-rubric: LLM output matches a given rubric, using a Language Model to grade output
rouge-n: Rouge-N score is above a given threshold
levenshtein: Levenshtein distance is below a threshold


To run eval, 
$ promptfoo eval

View result in the web browser
 promptfoo view