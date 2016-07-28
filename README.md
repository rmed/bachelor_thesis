# Bachelor Thesis

Code of my bachelor thesis "*Migration system for Zoe microservices*".

## Directory structure

The directories shown are supposed to be pasted on top of a Zoe installation
(see <https://github.com/voiser/zoe-startup-kit>) with some exceptions, such as
the dashboard.

The following is a comprehensive list of the contents:

```
agents/
    outpostest/     -> simple agent used to test the system
    scout/          -> agent in charge of managing outposts and migrations

cmdproc/
    scout.py        -> natural language commands for the Scout

dashboard/          -> code for the GTK+ secondary visualization GUI

lib/                -> Zoe library addition to enable migrations (Python)

mailproc/
    scout.py        -> natural language commands for the Scout (mailing)

outpost/
    outpost.sh      -> outpost launcher
    outpost/        -> outpost microserver code
```

## License

The code in this repository uses two licenses:

- **GPLv3**: Scout, outpost, Dashboard
- **MIT**: library addition (`lib/`)
