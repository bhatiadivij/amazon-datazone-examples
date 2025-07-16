from typing import List

from business.AWSClientFactory import AWSClientFactory
from utils.common_utils import get_collibra_synced_glossary_name, wait_until
from utils.env_utils import SMUS_DOMAIN_ID, SMUS_PRODUCER_PROJECT_ID, SMUS_CONSUMER_PROJECT_ID


class SMUSAdapter:
    def __init__(self, logger):
        self.__logger = logger
        self.__client = AWSClientFactory.create('datazone')

    def get_project(self, project_id):
        return self.__client.get_project(
            domainIdentifier=SMUS_DOMAIN_ID,
            identifier=project_id
        )

    def create_or_get_glossary(self) -> str:
        """
        Creates glossary in SMUS if it doesn't exist
        :return: Glossary id
        """
        glossary_name = get_collibra_synced_glossary_name()
        self.__logger.info(f"Using glossary with name: {glossary_name}")
        search_response = self.__client.search(domainIdentifier=SMUS_DOMAIN_ID,
                                               searchText=get_collibra_synced_glossary_name(),
                                               searchScope='GLOSSARY')
        if len(search_response['items']) > 0:
            for item in search_response['items']:
                if item['glossaryItem']['name'] == glossary_name:
                    return item['glossaryItem']['id']

        response = self.__client.create_glossary(
            description='Glossary for terms synced from Collibra',
            domainIdentifier=SMUS_DOMAIN_ID,
            name=get_collibra_synced_glossary_name(),
            owningProjectIdentifier=SMUS_PRODUCER_PROJECT_ID,
            status='ENABLED'
        )

        wait_until(2, 5, self.__logger, "Waiting for glossary to create", None)
        return response['id']

    def search_glossary_term_by_name(self, glossary_id: str, glossary_term_name: str):
        terms = self.__client.search(searchScope='GLOSSARY_TERM',
                                     domainIdentifier=SMUS_DOMAIN_ID,
                                     filters={"filter": {"attribute": "BusinessGlossaryTermForm.businessGlossaryId",
                                                       "value": glossary_id}},
                                     searchText=glossary_term_name,
                                     maxResults=50
                                     )['items']

        if terms:
            for term in terms:
                if term['glossaryTermItem']["name"] == glossary_term_name:
                    return term['glossaryTermItem']

        return None

    def create_glossary_term(self, glossary_id: str, name: str, descriptions: List[str]):
        self.__client.create_glossary_term(
            domainIdentifier=SMUS_DOMAIN_ID,
            glossaryIdentifier=glossary_id,
            name=name,
            status='ENABLED', **self.__get_description_args_of_glossary_term(descriptions)
        )

    def update_glossary_term_description(self, glossary_term_id: str, descriptions: List[str]):
        self.__client.update_glossary_term(
            domainIdentifier=SMUS_DOMAIN_ID,
            identifier=glossary_term_id,
            status='ENABLED', **self.__get_description_args_of_glossary_term(descriptions)
        )

    def search_all_assets_by_name(self, table_name: str):
        items = []
        next_token = None
        has_more_items = True
        while has_more_items:
            search_response = self.search_asset_by_name(table_name, next_token)
            items.extend(search_response['items'])
            next_token = search_response.get('nextToken', None)

            if not next_token or len(search_response['items']) == 0:
                has_more_items = False
        return items

    def search_asset_by_name(self, table_name: str, next_token: str = None):
        args = {"searchScope": 'ASSET', "owningProjectIdentifier": SMUS_PRODUCER_PROJECT_ID,
                "domainIdentifier": SMUS_DOMAIN_ID,
                "searchText": table_name
                }

        if next_token:
            args['nextToken'] = next_token

        return self.__client.search(**args)

    def search_all_listings(self, search_text: str = None):
        items = []
        next_token = None
        has_more_items = True
        while has_more_items:
            search_response = self.search_listings(search_text, next_token)
            items.extend(search_response['items'])
            next_token = search_response.get('nextToken', None)

            if not next_token or len(search_response['items']) == 0:
                has_more_items = False
        return items

    def search_listings(self, search_text: str = None, next_token: str = None):
        args = {"domainIdentifier": SMUS_DOMAIN_ID,
                "additionalAttributes": ["FORMS"],
                "filters": {
                    "and": [{"filter": {"attribute": "owningProjectId", "value": SMUS_PRODUCER_PROJECT_ID}},
                            {"filter": {"attribute": "amazonmetadata.sourceCategory", "value": "asset"}}]}
                }

        if search_text:
            args['searchText'] = search_text

        if next_token:
            args['nextToken'] = next_token

        return self.__client.search_listings(**args)

    def list_all_terms_in_glossary(self, glossary_id: str):
        items = []
        next_token = None
        has_more_items = True
        while has_more_items:
            search_response = self.list_terms_in_glossary(glossary_id, next_token)
            items.extend(search_response['items'])
            next_token = search_response.get('nextToken', None)

            if not next_token or len(search_response['items']) == 0:
                has_more_items = False
        return items

    def list_terms_in_glossary(self, glossary_id: str, next_token: str = None):
        args = {
            "searchScope": 'GLOSSARY_TERM',
            "domainIdentifier": SMUS_DOMAIN_ID,
            "filters": {"filter": {"attribute": "BusinessGlossaryTermForm.businessGlossaryId",
                                   "value": glossary_id}},
            "maxResults": 50,
        }

        if next_token:
            args['nextToken'] = next_token

        return self.__client.search(**args)

    def list_all_users_in_project(self, project_id: str):
        items = []
        next_token = None
        has_more_items = True
        while has_more_items:
            search_response = self.list_users_in_project(project_id, next_token)
            items.extend(search_response['members'])
            next_token = search_response.get('nextToken', None)

            if not next_token or len(search_response['members']) == 0:
                has_more_items = False
        return items

    def list_users_in_project(self, project_id: str, next_token: str = None):
        args = {
            "domainIdentifier":SMUS_DOMAIN_ID,
            "projectIdentifier":project_id,
            "maxResults": 50
        }

        if next_token:
            args['nextToken'] = next_token

        response = self.__client.list_project_memberships(**args)
        sso_users = []
        for member in response['members']:
            if 'user' in member['memberDetails']:
                sso_users.append(member)

        response['members'] = sso_users
        return response

    def get_sso_user_profile(self, user_id: str):
        return self.__client.get_user_profile(
            domainIdentifier=SMUS_DOMAIN_ID,
            userIdentifier=user_id
        )

    def get_asset(self, asset_id: str):
        return self.__client.get_asset(
            domainIdentifier=SMUS_DOMAIN_ID,
            identifier=asset_id)

    def create_asset_revision(self, asset_name, asset_id, forms_input, **optional_args):
        return self.__client.create_asset_revision(name=asset_name, domainIdentifier=SMUS_DOMAIN_ID,
                                                   formsInput=forms_input,
                                                   identifier=asset_id, **optional_args)

    def update_glossary_term_relations(self, glossary_id: str, id: str, name: str, term_relations: List[str]):
        return self.__client.update_glossary_term(
            domainIdentifier=SMUS_DOMAIN_ID,
            glossaryIdentifier=glossary_id,
            name=name,
            termRelations=term_relations,
            identifier=id,
            status='ENABLED',
        )

    def create_subscription_request(self, listing_id: str):
        return self.__client.create_subscription_request(
            domainIdentifier=SMUS_DOMAIN_ID,
            requestReason='Automated sync - Subscription request created from Collibra',
            subscribedListings=[
                {
                    'identifier': listing_id
                },
            ],
            subscribedPrincipals=[
                {
                    'project': {
                        'identifier': SMUS_CONSUMER_PROJECT_ID
                    }
                },
            ]
        )

    def search_subscription_requests(self, listing_id: str):
        return self.__client.list_subscription_requests(
            approverProjectId=SMUS_PRODUCER_PROJECT_ID,
            domainIdentifier=SMUS_DOMAIN_ID,
            owningProjectId=SMUS_CONSUMER_PROJECT_ID,
            status='ACCEPTED',
            sortBy='UPDATED_AT',
            sortOrder='DESCENDING',
            subscribedListingId=listing_id
        )['items']

    def search_approved_subscription_for_subscription_request_id(self, subscription_request_id):
        return self.__client.list_subscriptions(
            approverProjectId=SMUS_PRODUCER_PROJECT_ID,
            domainIdentifier=SMUS_DOMAIN_ID,
            owningProjectId=SMUS_CONSUMER_PROJECT_ID,
            status='APPROVED',
            subscriptionRequestIdentifier=subscription_request_id
        )['items']

    def accept_subscription_request(self, subscription_request_id: str):
        return self.__client.accept_subscription_request(
            decisionComment='Automated sync - Subscription request approved from Collibra',
            domainIdentifier=SMUS_DOMAIN_ID,
            identifier=subscription_request_id
        )

    def __get_description_args_of_glossary_term(self, term_descriptions: List[str]):
        description_args = {}
        if not term_descriptions:
            pass
        elif len(term_descriptions) == 1 and len(term_descriptions[0]) <= 1024:
            description_args['shortDescription'] = term_descriptions[0]
        else:
            description_args['longDescription'] = '\n\n'.join(term_descriptions)
        return description_args
