#include <jsmn_helpers.h>
#include <string.h>
#include <stdio.h>
#include <spiflash.h>

int json_token_check(const char *json_buffer, jsmntok_t *token, const char *searched)
{
	if ((int)strlen(searched) == token->end - token->start && strncmp(json_buffer + token->start, searched, token->end - token->start) == 0)
	{
		return 0; //Token found
	}
	return -1;
}

int print_tokens(char *json_buffer, const char *searched)
{
	int token_count;
	jsmn_parser parser;
	jsmntok_t tokens[JSMN_TOKEN_SIZE]; /* No more than JSMN_TOKEN_SIZE tokens */
	jsmn_init(&parser);
	token_count = jsmn_parse(&parser, json_buffer, strlen(json_buffer), tokens, sizeof(tokens) / sizeof(tokens[0]));
	if (token_count < 0)
	{
		printf("Failed to parse JSON\n");
		return -1;
	}
	for (unsigned i = 1; i < token_count; i++)
	{
		if(searched == NULL)
			printf("%.*s: %.*s\n",tokens[i].end - tokens[i].start, json_buffer + tokens[i].start ,tokens[i + 1].end - tokens[i + 1].start, json_buffer + tokens[i + 1].start);
		else if(json_token_check(json_buffer, &tokens[i], searched) == 0)
		{
			printf("%.*s: %.*s\n",tokens[i].end - tokens[i].start, json_buffer + tokens[i].start ,tokens[i + 1].end - tokens[i + 1].start, json_buffer + tokens[i + 1].start);
			return 0;
		}
		++i;
	}
	return 0;
}
