import copy
import math
import torch

from modules.utils import format_context

# Global dictionary to store initial probabilities
initial_phrase_probabilities = {}

def calculate_joint_log_probability(model, tokenizer, context, phrase):
    sequence = context + phrase
    sequence_input_ids = tokenizer.encode(sequence, return_tensors="pt").to("cuda")
    
    with torch.no_grad():
        outputs = model(sequence_input_ids)
        logits = outputs.logits

    phrase_tokens = tokenizer.encode(phrase, add_special_tokens=False)
    joint_log_prob = 0.0
    context_len = len(sequence_input_ids[0]) - len(phrase_tokens)

    for i, token_id in enumerate(phrase_tokens):
        word_log_prob = torch.log_softmax(logits[0, context_len + i - 1], dim=0)[token_id].item()
        joint_log_prob += word_log_prob

    return joint_log_prob

def print_phrase_probabilities(model, tokenizer, bad_phrases, good_phrases, device):
    global initial_phrase_probabilities

    if device != "cuda":
        model_copy = copy.deepcopy(model).to('cuda')
    else:
        model_copy = model

    print("\n---------------------------------------------------------------------------------------")
    print("| Type | Phrase             | Context                  | Probability   | Change       |")
    print("---------------------------------------------------------------------------------------")

    for phrase_type, phrase_list in [("BAD", bad_phrases), ("GOOD", good_phrases)]:
        for entry in phrase_list:
            phrase = entry['phrase']
            weight = entry['weight']
            contexts = entry['contexts']

            for context in contexts:
                joint_log_prob = calculate_joint_log_probability(model_copy, tokenizer, context, phrase)
                joint_prob = math.exp(joint_log_prob)  # Convert log probability to regular probability
                weighted_prob = joint_prob * weight
                prob_percentage = weighted_prob * 100  # Convert to percentage
                prob_str = f"{prob_percentage:.2f}%"  # Format as a percentage with 4 decimal places
                if weight != 1:
                    prob_str += "*"

                formatted_context = format_context(context, 24)
                formatted_phrase = format_context(phrase, 18)
                phrase_context_key = (phrase, context)

                if phrase_context_key not in initial_phrase_probabilities:
                    initial_phrase_probabilities[phrase_context_key] = joint_prob
                    print(f"| {phrase_type.ljust(4)} | {formatted_phrase} | {formatted_context} | {prob_str.ljust(13)} | {'N/A'.ljust(12)} |")
                else:
                    initial_prob = initial_phrase_probabilities[phrase_context_key]
                    change = ((joint_prob - initial_prob) * 100) * weight
                    change_str = f"{change:+.2f}%".ljust(12)
                    print(f"| {phrase_type.ljust(4)} | {formatted_phrase} | {formatted_context} | {prob_str.ljust(13)} | {change_str} |")

    print("---------------------------------------------------------------------------------------")
    print("* = Weighted probability\n")

    if device != "cuda":
        del model_copy
        torch.cuda.empty_cache()
        gc.collect()

def calculate_word_probabilities(model, tokenizer, bad_phrases, good_phrases, device):
    if device != "cuda":
        model_copy = copy.deepcopy(model).to('cuda')
    else:
        model_copy = model

    phrase_probs = []

    for phrase_list, sign in [(bad_phrases, 1), (good_phrases, -1)]:
        for entry in phrase_list:
            phrase = entry['phrase']
            weight = entry['weight']
            contexts = entry['contexts']
            for context in contexts:
                joint_log_prob = calculate_joint_log_probability(model_copy, tokenizer, context, phrase)
                joint_prob = math.exp(joint_log_prob)  # Convert log probability to regular probability
                weighted_prob = joint_prob * weight
                # Store the phrase and its weighted probability
                phrase_probs.append((phrase, weighted_prob))

    if device != "cuda":
        del model_copy
        torch.cuda.empty_cache()
        gc.collect()

    return phrase_probs #Good 의 확률이 적어지도록 유도? DPO처럼 Merge 가능성. Bad에 RP에 더해 복잡한 추론 포함, GOOD에 복잡하기만 하고 잘못된 정보넣기?