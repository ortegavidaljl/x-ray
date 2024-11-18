from enum import Enum

class EmailScore:
	def __init__(self):
		self.email_score = 10
		self.email_score_breakdown = {}

		def subtract(test, number):
			self.email_score = self.email_score - number
			self.email_score_breakdown[test] = number
			return number
		
class Score(Enum):
	SPAMASSASSIN_SPAM = 3
	SPF_ERR = 3
	SPF_WARN = 1.5
	MX_WARN = 1
	RDNS_WARN = 1
	DKIM_NO = 1
	DKIM_ERR = 3
	RBL_ERR = 1.5