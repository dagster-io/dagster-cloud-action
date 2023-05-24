import sys, os, logging
print(f"sys.executable={sys.executable}")
print(f"PYTHONPATH={os.getenv('PYTHONPATH')}")

try:
    import github
except:
    logging.exception("Cannot import github")
else:
    print(f"github.__path__={github.__path__}")

try:
    from github import Github
except:
    logging.exception("Cannot 'from github import Github'")
else:
    print(f"Github={Github}")