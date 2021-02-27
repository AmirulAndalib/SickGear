#!/usr/bin/python

# TVMaze Free endpoints
show_search = 'https://api.tvmaze.com/search/shows?q={0}'
show_single_search = 'https://api.tvmaze.com/singlesearch/shows?q={0}'
lookup_tvrage = 'https://api.tvmaze.com/lookup/shows?tvrage={0}'
lookup_tvdb = 'https://api.tvmaze.com/lookup/shows?thetvdb={0}'
lookup_imdb = 'https://api.tvmaze.com/lookup/shows?imdb={0}'
get_schedule = 'https://api.tvmaze.com/schedule?country={0}&date={1}'
get_full_schedule = 'https://api.tvmaze.com/schedule/full'
show_main_info = 'https://api.tvmaze.com/shows/{0}'
episode_list = 'https://api.tvmaze.com/shows/{0}/episodes'
episode_by_number = 'https://api.tvmaze.com/shows/{0}/episodebynumber?season={1}&number={2}'
episodes_by_date = 'https://api.tvmaze.com/shows/{0}/episodesbydate?date={1}'
show_cast = 'https://api.tvmaze.com/shows/{0}/cast'
show_index = 'https://api.tvmaze.com/shows?page={0}'
people_search = 'https://api.tvmaze.com/search/people?q={0}'
person_main_info = 'https://api.tvmaze.com/people/{0}'
person_cast_credits = 'https://api.tvmaze.com/people/{0}/castcredits'
person_crew_credits = 'https://api.tvmaze.com/people/{0}/crewcredits'
show_crew = 'https://api.tvmaze.com/shows/{0}/crew'
show_updates = 'https://api.tvmaze.com/updates/shows'
show_akas = 'https://api.tvmaze.com/shows/{0}/akas'
show_seasons = 'https://api.tvmaze.com/shows/{0}/seasons'
season_by_id = 'https://api.tvmaze.com/seasons/{0}'
episode_by_id = 'https://api.tvmaze.com/episodes/{0}'
show_images = 'https://api.tvmaze.com/shows/{0}/images'

# TVMaze Premium endpoints
followed_shows = 'https://api.tvmaze.com/v1/user/follows/shows{0}'
followed_people = 'https://api.tvmaze.com/v1/user/follows/people{0}'
followed_networks = 'https://api.tvmaze.com/v1/user/follows/networks{0}'
followed_web_channels = 'https://api.tvmaze.com/v1/user/follows/webchannels{0}'
marked_episodes = 'https://api.tvmaze.com/v1/user/episodes{0}'
voted_shows = 'https://api.tvmaze.com/v1/user/votes/shows{0}'
voted_episodes = 'https://api.tvmaze.com/v1/user/votes/episodes{0}'
