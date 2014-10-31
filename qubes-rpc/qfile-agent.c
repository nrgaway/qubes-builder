#include "qfile-utils.h"

char *get_abs_path(const char *cwd, const char *pathname)
{
	char *ret;
	if (pathname[0] == '/')
		return strdup(pathname);
	if (asprintf(&ret, "%s/%s", cwd, pathname) < 0)
		return NULL;
	else
		return ret;
}

int do_fs_walk(const char *file)
{
	char *newfile;
	struct stat st;
	struct dirent *ent;
	DIR *dir;

	if (lstat(file, &st))
		gui_fatal("stat %s", file);
	single_file_processor(file, &st);
	if (!S_ISDIR(st.st_mode))
		return 0;
	dir = opendir(file);
	if (!dir)
		gui_fatal("opendir %s", file);
	while ((ent = readdir(dir))) {
		char *fname = ent->d_name;
		if (!strcmp(fname, ".") || !strcmp(fname, ".."))
			continue;
		if (asprintf(&newfile, "%s/%s", file, fname) >= 0) {
			do_fs_walk(newfile);
			free(newfile);
		} else {
			fprintf(stderr, "asprintf failed\n");
			exit(1);
		}
	}
	closedir(dir);
	// directory metadata is resent; this makes the code simple,
	// and the atime/mtime is set correctly at the second time
	single_file_processor(file, &st);
	return 0;
}

int main(int argc, char **argv)
{
	int i;
	char *entry;
	char *cwd;
	char *sep;

	signal(SIGPIPE, SIG_IGN);
	register_notify_progress(&notify_progress);
	notify_progress(0, PROGRESS_FLAG_INIT);
	crc32_sum = 0;
	cwd = getcwd(NULL, 0);
	for (i = 1; i < argc; i++) {
		if (strcmp(argv[i], "--ignore-symlinks")==0) {
			ignore_symlinks = 1;
			continue;
		}

		entry = get_abs_path(cwd, argv[i]);

		do {
			sep = rindex(entry, '/');
			if (!sep)
				gui_fatal
				    ("Internal error: nonabsolute filenames not allowed");
			*sep = 0;
		} while (sep[1] == 0);
		if (entry[0] == 0) {
			if (chdir("/") < 0) {
				gui_fatal("Internal error: chdir(\"/\") failed?!");
			}
		} else if (chdir(entry))
			gui_fatal("chdir to %s", entry);
		do_fs_walk(sep + 1);
		free(entry);
	}
	notify_end_and_wait_for_result();
	notify_progress(0, PROGRESS_FLAG_DONE);
	return 0;
}


