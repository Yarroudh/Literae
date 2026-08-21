export type ResearchFilters = {
  query: string;
  fromYear: string;
  toYear: string;
  workType: string;
  openAccess: string;
  language: string;
  author: string;
  institution: string;
  source: string;
  sort: string;
  resultsLimit: string;
};

export type ResearchResult = {
  id: string;
  title: string;
  authors: string[];
  year: number;
  source: string;
  type: string;
  openAccess: boolean;
  citedByCount: number;
  topics: string[];
  summary: string;
  doi?: string | null;
};

export type AuthorResult = {
  id: string;
  name: string;
  orcid?: string | null;
  worksCount: number;
  citedByCount: number;
  hIndex: number;
  i10Index: number;
  affiliations: string[];
  topics: string[];
  openAlexUrl: string;
};
