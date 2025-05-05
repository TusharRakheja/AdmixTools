#include <stdio.h>
#include <string.h>

#include "geno.h"

struct arguments {
    char *input_file;
    char *output_file;
    int low_mem;
};

static void print_usage(const char *progname) {
    printf("Usage: %s [-m] input_genotype_file output_genotype_file\n", progname);
    printf("  -m: low-mem mode, do not allocate memory for the full genotype file\n");
}

int main(int argc, char **argv) {
    struct arguments arguments;
    arguments.low_mem = 0;
    arguments.input_file = NULL;
    arguments.output_file = NULL;

    int arg_index = 1;

    // Parse optional flags first
    while (arg_index < argc && argv[arg_index][0] == '-') {
        if (strcmp(argv[arg_index], "-m") == 0) {
            arguments.low_mem = 1;
        } else {
            print_usage(argv[0]);
            return -1;
        }
        arg_index++;
    }

    // Parse positional arguments
    if (argc - arg_index != 2) {
        print_usage(argv[0]);
        return -1;
    }

    arguments.input_file = argv[arg_index];
    arguments.output_file = argv[arg_index + 1];

    genotype_matrix geno;
    printf("reading %s\n", arguments.input_file);
    genotype_matrix_initialize(&geno);

    int result;
    if (arguments.low_mem) {
        result = genotype_matrix_read_file(&geno, arguments.input_file, 0, NULL, NULL);
    } else {
        result = genotype_matrix_read_file_full(&geno, arguments.input_file, 0, NULL, NULL);
    }

    if (result < 0) {
        printf("Error %d\n", result);
        return result;
    }

    genotype_matrix_write_packed_file(&geno, arguments.output_file, !geno.transpose);

    genotype_matrix_destructor(&geno);
    return 0;
}
