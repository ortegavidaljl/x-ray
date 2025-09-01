from enum import Enum
from utils.config import SCORE_DKIM_ERR, SCORE_DKIM_NO, SCORE_MX_WARN, SCORE_RBL_ERR, SCORE_RDNS_WARN, SCORE_RSPAMD_SPAM, SCORE_CLAMAV_VIRUS, SCORE_SPF_ERR, SCORE_SPF_WARN, SCORE_DMARC_ERR

class EmailScore:
	def __init__(self):
		self.email_score = 10
		self.email_score_breakdown = {}

	def subtract(self, test, number):
		self.email_score = self.email_score - number
		self.email_score_breakdown[test] = number
		return number
		
class Score(Enum):
	RSPAMD_SPAM = SCORE_RSPAMD_SPAM
	CLAMAV_VIRUS = SCORE_CLAMAV_VIRUS
	SPF_ERR = SCORE_SPF_ERR
	SPF_WARN = SCORE_SPF_WARN
	DMARC_ERR = SCORE_DMARC_ERR
	MX_WARN = SCORE_MX_WARN
	RDNS_WARN = SCORE_RDNS_WARN
	DKIM_NO = SCORE_DKIM_NO
	DKIM_ERR = SCORE_DKIM_ERR
	RBL_ERR = SCORE_RBL_ERR