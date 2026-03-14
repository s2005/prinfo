# Initial Prompt

I would like to implement Python project to grab information from PR using
gh cli. we need to check if gh cli installed on current machine and fail if
not. Python project is CLI app which should be well structured, use pytests
and uv package manager, .gitignore. prinfo python cli app should work on
Windows, Linux, MacOS. It should use argparse and logging ilbraries. in
first version we need to get logs from checks ran as part of PR and save it
in specific folder. we need to use different accounts for gh cli and it
should be specified as input parameters or as configuration values from
.env (some.env) file. env files should not be tracked by git. we need to
create private github repo using creads below.

- For initialization of local git repository please use following settings -

```bash
git config --local user.name "s2005"
git config --local user.email "s2005@users.noreply.github.com"
```

We should document all made changes as tasks at docs/tasks with specific
subfolder. save my initial prompt in docs/tasks/initial as md file as md
file. then prepare detailed PRD.md in the same folder and ask me to review
it when it done.
