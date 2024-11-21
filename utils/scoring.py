from enum import Enum
from utils.config import SCORE_DKIM_ERR, SCORE_DKIM_NO, SCORE_MX_WARN, SCORE_RBL_ERR, SCORE_RDNS_WARN, SCORE_SPAMASSASSIN_SPAM, SCORE_SPF_ERR, SCORE_SPF_WARN

class EmailScore:
	def __init__(self):
		self.email_score = 10
		self.email_score_breakdown = {}

	def subtract(self, test, number):
		self.email_score = self.email_score - number
		self.email_score_breakdown[test] = number
		return number
		
class Score(Enum):
	SPAMASSASSIN_SPAM = SCORE_SPAMASSASSIN_SPAM
	SPF_ERR = SCORE_SPF_ERR
	SPF_WARN = SCORE_SPF_WARN
	MX_WARN = SCORE_MX_WARN
	RDNS_WARN = SCORE_RDNS_WARN
	DKIM_NO = SCORE_DKIM_NO
	DKIM_ERR = SCORE_DKIM_ERR
	RBL_ERR = SCORE_RBL_ERR