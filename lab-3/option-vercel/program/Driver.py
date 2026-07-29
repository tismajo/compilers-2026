import sys
import os
from antlr4 import *
from SiteLangLexer import SiteLangLexer
from SiteLangParser import SiteLangParser
from SiteListener import SiteDeployListener

def main(argv):
    github_token = os.environ.get("GITHUB_TOKEN", "")
    vercel_token = os.environ.get("VERCEL_TOKEN", "")
    if not github_token or not vercel_token:
        print("Error: GITHUB_TOKEN and VERCEL_TOKEN must be set in your .env file.")
        sys.exit(1)

    input_stream = FileStream(argv[1], encoding="utf-8")
    lexer = SiteLangLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = SiteLangParser(stream)
    tree = parser.site()

    listener = SiteDeployListener(github_token, vercel_token)
    walker = ParseTreeWalker()
    walker.walk(listener, tree)
    listener.deploy()

if __name__ == "__main__":
    main(sys.argv)
