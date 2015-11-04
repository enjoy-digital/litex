
# Sending Patches

MiSoC does **not** use GitHub pull requests. Instead you must send patches to
the public mailing list <devel@lists.m-labs.hk>.

Before sending patches, please read the rest of this guide and make sure your
patch meets the following criteria;

 - [ ] Meets style guide requirements listed below.
 - [ ] Includes a suitable commit message.

Sending mail to the mailing list can be done via the `git send-email` tool.
The `git send-email` tool is not included by default on many Linux
distributions, on Ubuntu / Debian systems you may need to install the
`git-email` package. Documentation on using this tool can be found at
http://git-scm.com/docs/git-send-email

To send patches to the mailing list you must first be subscribed to the list.
You can subscribe at https://ssl.serverraum.org/lists/listinfo/devel

An example session would be;
```
# Set up [sendemail] as described at http://git-scm.com/docs/git-send-email in
# the EXAMPLE section.

# Download, make changes to misoc and commit them
git clone https://github.com/m-labs/misoc
cd misoc
edit xxx.py
git commit -a

# Send patch to mailing list
# --------------------------
# 1) Remove any previous outgoing patch
rm -rf outgoing

# 2) Put the patches to be sent into the outgoing directory
git format-patch --cover-letter -M origin/master -o outgoing/

# 3) Edit the cover letter with information about the patch
edit outgoing/0000-*

# 4) Actually send the email.
git send-email --to=devel@lists.m-labs.hk outgoing/*
```

# Help

If your submission is large and complex and/or you are not sure how to proceed,
feel free to discuss it on the mailing list or IRC (#m-labs on Freenode)
beforehand.

# Style Guide

All code should be compliant with the
[PEP8 style guide](https://www.python.org/dev/peps/pep-0008/).

You can use the [pep8 tool](https://www.python.org/dev/peps/pep-0008/) to check
compliance with `pep8 myfile.py`

When modifying existing code **be consistent** with any existing code style.

# License

All new contributions should be under the same license as MiSoC. This is a very
permissive two-clause BSD license. Full license text can be found at
https://github.com/m-labs/misoc/blob/master/LICENSE
