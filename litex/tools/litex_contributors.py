#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2021 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Small tool to easily update CONTRIBUTORS.

import os
import sys
import csv
import argparse

# Helpers ------------------------------------------------------------------------------------------

def make_unique(sequence):
    seen = set()
    return [x for x in sequence if not (x in seen or seen.add(x))]

class Author:
    def __init__(self, email, year):
        self.email = email
        self.years = [year]

    def add_year(self, year):
        self.years.append(year)
        self.years = make_unique(self.years)

# Use Git Log + Processing to create the list of Contibutors ---------------------------------------

companies = {
    "Antmicro" : "Antmicro.com",
    "Google"   : "Google.com",
}

def list_contributors(path):

    # Create .csv with git log.
    os.system(f"git log --follow --pretty=format:\"%an,%ae,%aI\" {path} | sort | uniq > contribs.csv")

    # Read .csv and process it.
    authors = {}
    with open("contribs.csv", newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter=",")
        for line in reader:
            name  = line[0]
            email = line[1]
            year  = line[2][:4]
            # For companies, replace individuals with company name/email.
            for companies_name, companies_email in companies.items():
                if companies_email.lower() in email:
                    name  = companies_name
                    email = companies_email
            if name in authors.keys():
                authors[name].add_year(int(year))
            else:
                authors[name] = Author(email, int(year))

    # Export Contributors.
    for name, info in authors.items():
        r = "Copyright (c) "
        if len(info.years) > 1:
            years = f"{info.years[0]}-{info.years[-1]}"
        else:
            years =  f"{info.years[0]}"
        r += years + " "*(9-len(years))
        r += " "
        r += name
        r += " <"
        r += info.email
        r += ">"
        print(r)

# Run ----------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Small tool to easily update CONTRIBUTORS.")
    parser.add_argument("--path", default="./", help="Git Path.")
    args = parser.parse_args()

    list_contributors(args.path)

if __name__ == "__main__":
    main()
