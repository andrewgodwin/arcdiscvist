RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"
BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = 30, 31, 32, 33, 34, 35, 36, 37

def color(color, text):
    return (COLOR_SEQ % color) + text + RESET_SEQ

def red(text):
    return color(RED, text)

def green(text):
    return color(GREEN, text)

def yellow(text):
    return color(YELLOW, text)

def cyan(text):
    return color(CYAN, text)
