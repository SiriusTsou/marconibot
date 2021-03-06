#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#    BTC: 13MXa7EdMYaXaQK6cDHqd4dwr2stBK3ESE
#    LTC: LfxwJHNCjDh2qyJdfu22rBFi2Eu8BjQdxj
#
#    https://github.com/s4w3d0ff/marconibot
#
#    Copyright (C) 2017  https://github.com/s4w3d0ff
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#!/usr/bin/python
from .tools import UTCstr2epoch, time, wait, logging, getMongoColl
from .tools.trading import autoRenewAll
from .tools import BL, OR, RD, GY, GR
from .tools import pymongo, roundDown, float2percent
from .tools.minion import Minion

logger = logging.getLogger(__name__)


class Loaner(Minion):
    """ Loanbot class [API REQUIRES KEY AND SECRET!]"""

    def __init__(self,
                 api,
                 coins={'BTC': 0.01},
                 maxage=60 * 5,
                 delay=60 * 3):
        self.api, self.delay = api, delay
        self.coins, self.maxage = coins, maxage
        self.db = getMongoColl('poloniex', 'lendingHistory')

    def getLoanOfferAge(self, order):
        return time() - UTCstr2epoch(order['date'])

    def cancelOldOffers(self):
        logger.info(GR("Checking Open Loan Offers:----------------"))
        offers = self.api.returnOpenLoanOffers()
        if len(offers) < 1:
            return logger.info(RD('No open loan offers found'))
        for coin in self.coins:
            if coin not in offers:
                continue
            for offer in offers[coin]:
                logger.info("%s|%s:%s-[rate:%s]",
                            BL(offer['date']),
                            OR(coin),
                            RD(offer['amount']),
                            GY(float2percent(offer['rate'])) + '%'
                            )
                if self.getLoanOfferAge(offer) > self.maxage:
                    logger.info("Canceling %s offer %s",
                                OR(coin), GY(offer['id']))
                    r = self.api.cancelLoanOffer(offer['id'])
                    logger.info(r['message'])

    def createLoanOffers(self):
        logger.info(GR("Checking for coins to lend:---------------"))
        bals = self.api.returnAvailableAccountBalances()
        if not 'lending' in bals:
            return logger.info(RD("No coins found in lending account"))
        for coin in self.coins:
            if coin not in bals['lending']:
                continue
            amount = bals['lending'][coin]
            if float(amount) < self.coins[coin]:
                logger.info("Not enough %s:%s, below set minimum: %s",
                            OR(coin),
                            RD(amount),
                            BL(self.coins[coin]))
                continue
            else:
                logging.info("%s:%s", OR(coin), GR(amount))
            orders = self.api.returnLoanOrders(coin)['offers']
            price = sum([float(o['rate']) for o in orders]) / len(orders)
            logger.info('Creating %s %s loan offer at %s',
                        RD(amount), OR(coin), GR(float2percent(price)) + '%')
            r = self.api.createLoanOffer(coin, amount, price, autoRenew=0)
            logger.info('%s', GR(r["message"]))

    def updateLendingHistory(self):
        try:
            old = list(self.db.find().sort('timestamp', pymongo.ASCENDING))[-1]
        except IndexError:
            logger.warning(RD('No loan history found in database'))
            old = {'timestamp': time() - self.api.YEAR * 10}
        start = old['timestamp'] + 1
        new = self.api.returnLendingHistory(start=start)
        if len(new) > 0:
            logger.info(GR('%d new lending database entries' % len(new)))
            for loan in new:
                _id = loan['id']
                del loan['id']
                loan['timestamp'] = UTCstr2epoch(loan['close'])
                loan['rate'] = float(loan['rate'])
                loan['duration'] = float(loan['duration'])
                loan['interest'] = float(loan['interest'])
                loan['fee'] = float(loan['fee'])
                loan['earned'] = float(loan['earned'])
                self.db.update_one({'_id': _id}, {'$set': loan}, upsert=True)

    def myLendingHistory(self):
        self.updateLendingHistory()
        for coin in self.coins:
            earned = 0
            duration = 0
            rates = []
            hist = list(self.db.find({'currency': coin}))
            if len(hist) > 0:
                logger.debug('%s past loan orders found for %s',
                             GR(len(hist)), OR(coin))
                for loan in hist:
                    earned += loan['earned']
                    duration += loan['duration']
                    rates.append(loan['rate'])

            logger.info(
                "Total %s earned lending: [earnings: %s] [average rate: %s]",
                OR(coin), GR(roundDown(earned)),
                BL(roundDown(sum(rates) / len(rates)))
            )

    def showActiveLoans(self):
        active = self.api.returnActiveLoans()['provided']
        logger.info(GR('Active Loans:-----------------------------'))
        for i in active:
            logger.info('%s|%s:%s-[rate:%s]-[fees:%s]',
                        BL(i['date']),
                        OR(i['currency']),
                        RD(i['amount']),
                        GY(roundDown(float2percent(i['rate']))) + '%',
                        GR(i['fees'])
                        )

    def run(self):
        """ Main loop, cancels 'stale' loan offers, turns auto - renew off on
        active loans, and creates new loan offers at optimum price """
        # Check auto renew is not enabled for current loans
        autoRenewAll(self.api, toggle=False)
        while self._running:
            try:
                # Check for old offers
                self.cancelOldOffers()
                # Create new offer (if can)
                self.createLoanOffers()
                # show active
                self.showActiveLoans()
                # show history
                self.myLendingHistory()

            except Exception as e:
                logger.exception(e)

            finally:
                # sleep with one eye open...
                for i in range(int(self.delay)):
                    if not self._running:
                        break
                    wait(1)
