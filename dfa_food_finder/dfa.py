import copy
import json
from flask import Blueprint, render_template, request, flash, redirect
from werkzeug.utils import secure_filename

bp = Blueprint("dfa", __name__)

ALLOWED_EXTENSIONS = ["txt"]
SPECIAL_ALPHABETS = [" ", "\n", "\t", "\r"]

# Get all the alphabet (Σ), a-z, A-Z, " " (white space), "\n", "\t", "\r"
def get_alphabet():
    alphabet = []
    for i in range(ord("a"), ord("z") + 1):
        alphabet.append(chr(i))
    for i in range(ord("A"), ord("Z") + 1):
        alphabet.append(chr(i))
    alphabet.extend(SPECIAL_ALPHABETS)
    return copy.deepcopy(alphabet)


# To build DFA from food.json
def create_dfa(food_list):
    dfa = {"-1": {}, "0": {}}
    final_states = {}
    space_state = set()
    word_length = []
    alphabet = get_alphabet()
    for a in alphabet:
        dfa["-1"][a] = "-1"
        dfa["0"][a] = "-1"

    for inputs in food_list:
        # To keep track of current and next state
        curr_state = "0"
        next_state = "0"
        for each_char in inputs:
            # For each iteration, assign previous next state to current state
            curr_state = next_state
            next_state = dfa.get(curr_state).get(each_char)
            # If '-1' (default) is in the next state
            if int(next_state) == -1:
                # Assign new state to the NFA by getting the max value of the state
                new_state = max([int(x) for x in list(dfa.keys())]) + 1
                new_state = str(new_state)
                # Assign the new state to DFA
                dfa[curr_state][str(each_char)] = new_state
                # Make the same for capital letter
                dfa[curr_state][str(each_char).upper()] = new_state
                # If the new state is not yet in the NFA, initialize it
                if new_state not in dfa.keys():
                    dfa[new_state] = {}
                    alphabet = get_alphabet()
                    for a in alphabet:
                        dfa[new_state][a] = "-1"
                next_state = new_state
            # Store the next state when character is " " (white space)
            if each_char == " ":
                space_state.add(next_state)
        final_states[next_state] = inputs
        word_length.append((next_state, len(inputs)))

    # For each of the state in space_state, assign addition transition to the states
    # where they start from initial state
    for each_space_state in space_state:
        same_keys = {}
        new_dfa = copy.deepcopy(dfa)
        for k, val in new_dfa.get("0").items():
            # For each state that is not point to -1
            if val != "-1":
                # If the next state for space state is also -1, assign new state to the space state
                if new_dfa.get(each_space_state).get(k) == "-1":
                    dfa[each_space_state][k] = val
                else:
                    if new_dfa.get(each_space_state).get(k) not in final_states:
                        same_keys[k] = [each_space_state, "0"]

        while len(same_keys.keys()) != 0:
            same_keys, dfa = follow_states(dfa, same_keys, final_states)
    
    # Change all the space transition to "0" instead of "-1"
    for st in dfa:
        if dfa.get(st).get(" ") == "-1":
            dfa[st][" "] = "0"
        # Change all the transition of "\n", "\t" and "\r" to "0"
        for special_chars in SPECIAL_ALPHABETS[1:]:
            dfa[st][special_chars] = "0"
    
    return copy.deepcopy(dfa), copy.deepcopy(final_states), copy.deepcopy(space_state), copy.deepcopy(word_length)


def follow_states(dfa, keys, final_states):
    new_keys = {}
    new_dfa = copy.deepcopy(dfa)
    final = list(final_states.keys())
    for key, val in keys.items():
        space_next_state = dfa.get(val[0]).get(key)
        start_next_state = dfa.get(val[1]).get(key)
        for k, v in dfa.get(start_next_state).items():
            if v != "-1":
                if dfa.get(space_next_state).get(k) == "-1":
                    new_dfa[space_next_state][k] = v
                else:
                    if dfa.get(space_next_state).get(k) not in final:
                        new_keys[k] = [space_next_state, start_next_state]
    return copy.deepcopy(new_keys), copy.deepcopy(new_dfa)


def allowed_file(filename):
    return '.' in filename and str(filename).rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@bp.app_template_filter("get_occurences")
def get_occurences(occurrences_dict, food_name):
    try:
        count = occurrences_dict.get(food_name, 0)
    except Exception:
        return "NA"
    return count


@bp.route("/", methods=["GET", "POST"])
def index():
    
    all_food = {}
    with open("food.json", "r") as f:
        all_food = json.load(f)
    
    filename = ""
    highlighted_text_file = ""
    status_value = "Reject"
    all_accepting_words = []
    occurrence_count = {}
    dfa = {}
    final = []
    all_states_index = []
    
    if request.method == "POST":
        text_input = ""
        final_states = {}
        # Create the DFA
        dfa, final_states, space_states, word_len = create_dfa(all_food.get("food"))
        # Check if the post request has the file part
        if "inputFile" not in request.files:
            flash("No file part", "error")
            return redirect(request.url)
        file = request.files["inputFile"]
        if file.filename == "":
            flash("No selected file", "error")
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            text_input = file.read()
            text_input = text_input.decode("utf-8")
        else:
            flash("Selected file extension is not allowed.", "error")
            return redirect(request.url)
        
        curr_state = "0"
        next_state = "0"
        final = list(final_states.keys())
        # Input alphabet
        alphabet = get_alphabet()
        # Initialize occurence count
        for _, food_val in final_states.items():
            occurrence_count[food_val] = 0
        # space_states is the start states for each accepted word, need to include the initial states '0'
        space_states.add("0")
        # Loop through each word in input text file
        for char_idx, each_char in enumerate(text_input):
            # Skip the character if it is not in the alphabet
            if each_char not in alphabet:
                continue
            curr_state = next_state
            all_states_index.append((curr_state, char_idx))
            if curr_state in final and each_char in SPECIAL_ALPHABETS:
                idx = get_accept_word_index(all_states_index, space_states, word_len)
                # Get the end position index of the word
                end_pos = all_states_index[-1][1]
                # Need to change the end position index if the end index is not 1 more than the previous word index
                # Because non-alphabet character are not includeds
                if all_states_index[-1][1] - 1 != all_states_index[-2][1]:
                    end_pos = all_states_index[-2][1] + 1
                all_accepting_words.append(
                    (
                        text_input[all_states_index[idx][1] : end_pos],
                        all_states_index[idx][1],
                        end_pos - 1
                    )
                )
                status_value = "Accept"
                # Increment the occurrence count for the food
                occurrence_count[final_states.get(curr_state)] += 1
            next_state = dfa.get(curr_state).get(each_char)
        # Need to repeat again because the ending of the DFA and ending of the text input is not the same
        all_states_index.append((next_state, -1))
        if next_state in final:
            idx = get_accept_word_index(all_states_index, space_states, word_len)
            end_pos = all_states_index[-1][1]
            if all_states_index[-1][1] - 1 != all_states_index[-2][1]:
                end_pos = all_states_index[-2][1] + 1
            all_accepting_words.append(
                (
                    text_input[all_states_index[idx][1] : end_pos],
                    all_states_index[idx][1],
                    end_pos - 1
                )
            )
            status_value = "Accept"
            occurrence_count[final_states.get(next_state)] += 1
        # Highlight the text input
        for i, char in enumerate(text_input):
            for _, s, e in all_accepting_words:
                if i == s:
                    highlighted_text_file += "<mark>"
            highlighted_text_file += char
            for _, _, e in all_accepting_words:
                if i == e:
                    highlighted_text_file += "</mark>"
        
        if len(all_states_index) > 1:
            flash("Results are generated successfully.", "success")
    
    return render_template(
        "home.html",
        filename=filename,
        food=all_food.get("food"),
        highlighted_text_file=highlighted_text_file,
        dfa_status=status_value,
        accepted_word=all_accepting_words,
        occurrences_count=occurrence_count,
        dfa=dfa,
        final_states=final,
        states_transition=all_states_index
    )


def get_accept_word_index(all_states, initial_states, word_len):
    start = 0
    idx = len(all_states) - 1
    curr_word_len = 1
    # Get the length of the accepted word
    stopping_length = 0
    for final, length in word_len:
        if final == all_states[-1][0]:
            stopping_length = length
            break
    # Reversed is used to get the nearest starting state
    for state, _ in reversed(all_states):
        # Retrieved index is the one start from 0 or space state
        # this is to prevent getting wrong words
        # e.g. 0 -> 1 -> 2 -> 3 (space state) -> 1 -> 2 -> 3 -> 4 -> 5 (final) -> ... -> ...
        # the correct sequence should be 3, 1, 2, 3, 4, 5, instead of 0, 1, 2, 3, 1, 2, 3, 4, 5
        if state in initial_states:
            if stopping_length + 1 == curr_word_len:
                start = idx
                break
        idx -= 1
        curr_word_len += 1
    return start
