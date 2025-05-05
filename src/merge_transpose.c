#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

#include "geno.h"

#define WVERSION "100"
#define GENO_HEADER_SIZE 16

struct arguments {
    char *input_file_list;
    char *output_file;
    unsigned int individual_hash;
    unsigned int snp_hash;
};

static void print_usage(const char *progname) {
    printf("Usage: %s -l input_list.txt -o output.geno [-i ind_hash] [-s snp_hash]\n", progname);
    printf("  -l FILE   : file containing list of genotype files to merge\n");
    printf("  -o FILE   : output genotype file\n");
    printf("  -i int    : individual hash (optional)\n");
    printf("  -s int    : SNP hash (optional)\n");
}

// Check if a file exists
bool file_exists(const char filename[]) {
    FILE *fp = fopen(filename, "r");
    bool exists = (fp != NULL);
    if (fp) fclose(fp);
    return exists;
}

// Add a single genotype file to the merged output
int add_geno(const char filename[], FILE *merged, genotype_matrix *combined_geno) {
    genotype_matrix to_add;
    int num_samples = 0;
    int expanded_filename_size = strlen(filename) + 5;
    char *file_to_open = malloc(expanded_filename_size);
    strncpy(file_to_open, filename, expanded_filename_size);

    if (file_to_open[strlen(filename)-1] == '\n')
        file_to_open[strlen(filename)-1] = '\0';

    if (!file_exists(file_to_open)) {
        strcat(file_to_open, ".geno");
    }

    printf("reading %s\n", file_to_open);
    genotype_matrix_initialize(&to_add);
    int result = genotype_matrix_read_file(&to_add, file_to_open, 0, NULL, NULL);
    if (result < 0 || !to_add.transpose) {
        fprintf(stderr, "Failed to add genotype file %s\n", file_to_open);
        free(file_to_open);
        exit(-1);
    }

    if (combined_geno->num_columns <= 0) {
        combined_geno->num_columns = to_add.num_columns;
    } else if (combined_geno->num_columns != to_add.num_columns) {
        fprintf(stderr, "SNP mismatch %zu %zu %s\n", combined_geno->num_columns, to_add.num_columns, file_to_open);
        free(file_to_open);
        exit(-1);
    }

    num_samples = to_add.num_rows;
    fwrite(to_add.genotypes, sizeof(unsigned char), genotype_matrix_byte_size(&to_add), merged);
    genotype_matrix_destructor(&to_add);
    free(file_to_open);
    return num_samples;
}

int main(int argc, char **argv) {
    struct arguments arguments;
    arguments.input_file_list = NULL;
    arguments.output_file = NULL;
    arguments.individual_hash = 0;
    arguments.snp_hash = 0;

    // Parse command-line arguments
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-l") == 0 && i + 1 < argc) {
            arguments.input_file_list = argv[++i];
        } else if (strcmp(argv[i], "-o") == 0 && i + 1 < argc) {
            arguments.output_file = argv[++i];
        } else if (strcmp(argv[i], "-i") == 0 && i + 1 < argc) {
            arguments.individual_hash = strtoul(argv[++i], NULL, 16);
        } else if (strcmp(argv[i], "-s") == 0 && i + 1 < argc) {
            arguments.snp_hash = strtoul(argv[++i], NULL, 16);
        } else {
            print_usage(argv[0]);
            return -1;
        }
    }

    if (!arguments.input_file_list || !arguments.output_file) {
        print_usage(argv[0]);
        return -1;
    }

    // Initialize combined genotype
    genotype_matrix combined;
    genotype_matrix_initialize(&combined);
    combined.transpose = true;
    if (arguments.individual_hash)
        combined.individual_file_hash = arguments.individual_hash;
    if (arguments.snp_hash)
        combined.snp_file_hash = arguments.snp_hash;

    // Open output file
    FILE *merged = fopen(arguments.output_file, "w+");
    if (!merged) {
        fprintf(stderr, "failed to open %s\n", arguments.output_file);
        return -1;
    }

    // Write placeholder header
    char header_buffer[GENO_HEADER_SIZE+1];
    memset(header_buffer, 0, GENO_HEADER_SIZE+1);
    genotype_matrix_header(&combined, true, header_buffer);
    fwrite(header_buffer, sizeof(char), GENO_HEADER_SIZE, merged);

    // Open input file list
    FILE *list_file = fopen(arguments.input_file_list, "r");
    if (!list_file) {
        fprintf(stderr, "failed to open %s\n", arguments.input_file_list);
        fclose(merged);
        return -1;
    }

    size_t len = 2048;
    char *filename = malloc(len);
    ssize_t read;

    // Merge each genotype file
    while ((read = getline(&filename, &len, list_file)) != -1) {
        int samples_added = add_geno(filename, merged, &combined);
        combined.num_rows += samples_added;
    }

    free(filename);

    // Rewrite header with final information
    fseek(merged, 0, SEEK_SET);
    genotype_matrix_header(&combined, true, header_buffer);
    fwrite(header_buffer, sizeof(char), GENO_HEADER_SIZE, merged);

    fclose(list_file);
    fclose(merged);

    return 0;
}
