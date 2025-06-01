import aiohttp
import asyncio
import re
import logging
from typing import Optional, Tuple

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CurrencyConverter:
    def __init__(self):
        self.crypto_api_url = "https://api.coingecko.com/api/v3/simple/price"
        self.fiat_api_url = "https://api.exchangerate-api.com/v4/latest/USD"
        
        # Common currency mappings
        self.currency_aliases = {
            'ngn': 'NGN', 'naira': 'NGN', 'nigeria': 'NGN',
            'usd': 'USD', 'dollar': 'USD', 'dollars': 'USD',
            'eur': 'EUR', 'euro': 'EUR', 'euros': 'EUR',
            'gbp': 'GBP', 'pound': 'GBP', 'pounds': 'GBP',
            'jpy': 'JPY', 'yen': 'JPY',
            'cad': 'CAD', 'canadian': 'CAD',
            'aud': 'AUD', 'australian': 'AUD',
            'chf': 'CHF', 'swiss': 'CHF',
            'cny': 'CNY', 'yuan': 'CNY', 'rmb': 'CNY',
            'inr': 'INR', 'rupee': 'INR', 'rupees': 'INR',
        }
        
        
        self.crypto_aliases = {
            'btc': 'bitcoin', 'bitcoin': 'bitcoin',
            'eth': 'ethereum', 'ethereum': 'ethereum',
            'usdt': 'tether', 'tether': 'tether',
            'bnb': 'binancecoin', 'binancecoin': 'binancecoin',
            'sol': 'solana', 'solana': 'solana',
            'ada': 'cardano', 'cardano': 'cardano',
            'xrp': 'ripple', 'ripple': 'ripple',
            'dot': 'polkadot', 'polkadot': 'polkadot',
            'doge': 'dogecoin', 'dogecoin': 'dogecoin',
            'avax': 'avalanche-2', 'avalanche': 'avalanche-2',
            'matic': 'matic-network', 'polygon': 'matic-network',
            'link': 'chainlink', 'chainlink': 'chainlink',
            'ltc': 'litecoin', 'litecoin': 'litecoin',
            'bch': 'bitcoin-cash', 'bitcoincash': 'bitcoin-cash',
            'uni': 'uniswap', 'uniswap': 'uniswap',
            'atom': 'cosmos', 'cosmos': 'cosmos',
            'xlm': 'stellar', 'stellar': 'stellar',
            'vet': 'vechain', 'vechain': 'vechain',
            'icp': 'internet-computer', 'internetcomputer': 'internet-computer',
            'fil': 'filecoin', 'filecoin': 'filecoin',
            'trx': 'tron', 'tron': 'tron',
            'etc': 'ethereum-classic', 'ethereumclassic': 'ethereum-classic',
            'xmr': 'monero', 'monero': 'monero',
            'algo': 'algorand', 'algorand': 'algorand',
            'hbar': 'hedera-hashgraph', 'hedera': 'hedera-hashgraph',
            'near': 'near', 'nearprotocol': 'near',
            'flow': 'flow', 'flowtoken': 'flow',
            'egld': 'elrond-erd-2', 'elrond': 'elrond-erd-2',
            'xtz': 'tezos', 'tezos': 'tezos',
            'theta': 'theta-token', 'thetatoken': 'theta-token',
            'klay': 'klay-token', 'klaytn': 'klay-token',
            'ftm': 'fantom', 'fantom': 'fantom',
            'one': 'harmony', 'harmony': 'harmony',
            'zil': 'zilliqa', 'zilliqa': 'zilliqa',
            'bat': 'basic-attention-token', 'basicattentiontoken': 'basic-attention-token',
            'enj': 'enjincoin', 'enjin': 'enjincoin',
            'mana': 'decentraland', 'decentraland': 'decentraland',
            'sand': 'the-sandbox', 'sandbox': 'the-sandbox',
            'axs': 'axie-infinity', 'axieinfinity': 'axie-infinity',
            'chz': 'chiliz', 'chiliz': 'chiliz',
            'gala': 'gala', 'galatoken': 'gala',
            'lrc': 'loopring', 'loopring': 'loopring',
            'imx': 'immutable-x', 'immutablex': 'immutable-x',
            'cro': 'crypto-com-chain', 'cryptocom': 'crypto-com-chain',
            'shib': 'shiba-inu', 'shibainu': 'shiba-inu',
            'pepe': 'pepe', 'pepecoin': 'pepe',
            'floki': 'floki', 'flokiinu': 'floki',
            'bonk': 'bonk', 'bonktoken': 'bonk',
            'wif': 'dogwifcoin', 'dogwifhat': 'dogwifcoin',
            
            'ton': 'the-open-network', 'toncoin': 'the-open-network', 'theopennetwork': 'the-open-network',
            'usdc': 'usd-coin', 'usdcoin': 'usd-coin',
            'steth': 'staked-ether', 'stakedether': 'staked-ether',
            'dai': 'dai', 'daitoken': 'dai',
            'wbtc': 'wrapped-bitcoin', 'wrappedbitcoin': 'wrapped-bitcoin',
            'leo': 'leo-token', 'leotoken': 'leo-token',
            'kas': 'kaspa', 'kaspa': 'kaspa',
            'sui': 'sui', 'suinetwork': 'sui',
            'apt': 'aptos', 'aptos': 'aptos',
            'arb': 'arbitrum', 'arbitrum': 'arbitrum',
            'op': 'optimism', 'optimism': 'optimism',
            'inj': 'injective-protocol', 'injective': 'injective-protocol',
            'sei': 'sei-network', 'seinetwork': 'sei-network',
            'tia': 'celestia', 'celestia': 'celestia',
            'wld': 'worldcoin-wld', 'worldcoin': 'worldcoin-wld',
            'jup': 'jupiter-exchange-solana', 'jupiter': 'jupiter-exchange-solana',
            'pyth': 'pyth-network', 'pythnetwork': 'pyth-network',
            'jto': 'jito-governance-token', 'jito': 'jito-governance-token',
            'wen': 'wen-4', 'wentoken': 'wen-4',
            'bome': 'book-of-meme', 'bookofmeme': 'book-of-meme',
            'popcat': 'popcat', 'popcattoken': 'popcat',
            'neiro': 'neiro', 'neirotoken': 'neiro',
            'goat': 'goatseus-maximus', 'goatseusmaximius': 'goatseus-maximus',
            'pnut': 'peanut-the-squirrel', 'peanut': 'peanut-the-squirrel',
            'act': 'act-i-the-ai-prophecy', 'actai': 'act-i-the-ai-prophecy',
            'moodeng': 'moo-deng', 'moodengtoken': 'moo-deng',
            'fartcoin': 'fartcoin', 'fart': 'fartcoin',
            'ai16z': 'ai16z', 'ai16ztoken': 'ai16z',
            'virtual': 'virtual-protocol', 'virtualprotocol': 'virtual-protocol',
            'griffain': 'griffain', 'griffaintoken': 'griffain',
            'zerebro': 'zerebro', 'zerebrotoken': 'zerebro',
            'eliza': 'eliza', 'elizatoken': 'eliza',
            'luna': 'terra-luna-2', 'terraluna': 'terra-luna-2',
            'lunc': 'terra-luna', 'lunac': 'terra-luna',
            'ustc': 'terrausd', 'terraclassicusd': 'terrausd',
            'fet': 'fetch-ai', 'fetchai': 'fetch-ai',
            'render': 'render-token', 'rendertoken': 'render-token',
            'grt': 'the-graph', 'thegraph': 'the-graph',
            'ocean': 'ocean-protocol', 'oceanprotocol': 'ocean-protocol',
            'agix': 'singularitynet', 'singularitynet': 'singularitynet',
        }

    def parse_conversion_command(self, text: str) -> Optional[Tuple[float, str, str]]:
        """Parse conversion command and extract amount, from_currency, to_currency"""
        try:
            text = text.strip()
            if text.startswith('/convert'):
                text = text.replace('/convert', '', 1).strip()
            elif text.startswith('/conv'):
                text = text.replace('/conv', '', 1).strip()
            elif text.startswith('/c '):
                text = text.replace('/c ', '', 1).strip()
            
            # Pattern 1: /conv 1600 ngn usd
            pattern1 = r'^(\d+(?:\.\d+)?)\s+([a-zA-Z]+)\s+([a-zA-Z]+)$'
            match1 = re.match(pattern1, text, re.IGNORECASE)
            
            if match1:
                amount = float(match1.group(1))
                from_curr = match1.group(2).lower()
                to_curr = match1.group(3).lower()
                return amount, from_curr, to_curr
            
            # Pattern 2: /conv 1600ngn usd
            pattern2 = r'^(\d+(?:\.\d+)?)([a-zA-Z]+)\s+([a-zA-Z]+)$'
            match2 = re.match(pattern2, text, re.IGNORECASE)
            
            if match2:
                amount = float(match2.group(1))
                from_curr = match2.group(2).lower()
                to_curr = match2.group(3).lower()
                return amount, from_curr, to_curr
            
            # Pattern 3: /conv 1600 ngn (default to USD)
            pattern3 = r'^(\d+(?:\.\d+)?)\s+([a-zA-Z]+)$'
            match3 = re.match(pattern3, text, re.IGNORECASE)
            
            if match3:
                amount = float(match3.group(1))
                from_curr = match3.group(2).lower()
                to_curr = 'usd'
                return amount, from_curr, to_curr
            
            # Pattern 4: /conv 1600ngn (default to USD)
            pattern4 = r'^(\d+(?:\.\d+)?)([a-zA-Z]+)$'
            match4 = re.match(pattern4, text, re.IGNORECASE)
            
            if match4:
                amount = float(match4.group(1))
                from_curr = match4.group(2).lower()
                to_curr = 'usd'
                return amount, from_curr, to_curr
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing conversion command: {e}")
            return None

    def normalize_currency(self, currency: str) -> Tuple[str, str]:
        """Normalize currency and determine if it's crypto or fiat"""
        currency = currency.lower().strip()
        
        # Check if it's a known crypto
        if currency in self.crypto_aliases:
            return self.crypto_aliases[currency], 'crypto'
        
        # Check if it's a known fiat currency
        if currency in self.currency_aliases:
            return self.currency_aliases[currency], 'fiat'
        
        # If not found in aliases, assume it might be a valid ticker
        # For crypto, use as-is (lowercase)
        # For fiat, use uppercase
        if len(currency) == 3:
            return currency.upper(), 'fiat'  # Assume 3-letter codes are fiat
        else:
            return currency.lower(), 'crypto'  # Assume longer names are crypto

    async def get_crypto_price(self, crypto_id: str, vs_currency: str = 'usd') -> Optional[float]:
        """Get cryptocurrency price from CoinGecko API"""
        try:
            vs_currency = vs_currency.lower()
            url = f"{self.crypto_api_url}?ids={crypto_id}&vs_currencies={vs_currency}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if crypto_id in data and vs_currency in data[crypto_id]:
                            return float(data[crypto_id][vs_currency])
            return None
        except Exception as e:
            logger.error(f"Error fetching crypto price for {crypto_id}: {e}")
            return None

    async def get_fiat_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Get fiat currency exchange rate"""
        try:
            from_currency = from_currency.upper()
            to_currency = to_currency.upper()
            
            if from_currency == to_currency:
                return 1.0
            
            # Use exchangerate-api for fiat conversions
            url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'rates' in data and to_currency in data['rates']:
                            return float(data['rates'][to_currency])
            return None
        except Exception as e:
            logger.error(f"Error fetching fiat rate from {from_currency} to {to_currency}: {e}")
            return None

    async def convert_currency(self, amount: float, from_curr: str, to_curr: str) -> Optional[dict]:
        """Main conversion function"""
        try:
            # Normalize currencies
            from_normalized, from_type = self.normalize_currency(from_curr)
            to_normalized, to_type = self.normalize_currency(to_curr)
            
            logger.info(f"Converting {amount} {from_curr} ({from_normalized}, {from_type}) to {to_curr} ({to_normalized}, {to_type})")
            
            conversion_rate = None
            
            # Crypto to Crypto
            if from_type == 'crypto' and to_type == 'crypto':
                logger.info(f"Crypto to crypto conversion: {from_normalized} -> {to_normalized}")
                # Convert both to USD first, then calculate rate
                from_usd_price = await self.get_crypto_price(from_normalized, 'usd')
                to_usd_price = await self.get_crypto_price(to_normalized, 'usd')
                
                logger.info(f"USD prices: {from_normalized}=${from_usd_price}, {to_normalized}=${to_usd_price}")
                
                if from_usd_price and to_usd_price:
                    conversion_rate = from_usd_price / to_usd_price
            
            # Crypto to Fiat
            elif from_type == 'crypto' and to_type == 'fiat':
                logger.info(f"Crypto to fiat conversion: {from_normalized} -> {to_normalized}")
                conversion_rate = await self.get_crypto_price(from_normalized, to_normalized.lower())
                logger.info(f"Conversion rate: {conversion_rate}")
            
            # Fiat to Crypto
            elif from_type == 'fiat' and to_type == 'crypto':
                logger.info(f"Fiat to crypto conversion: {from_normalized} -> {to_normalized}")
                crypto_price = await self.get_crypto_price(to_normalized, from_normalized.lower())
                logger.info(f"Crypto price in {from_normalized}: {crypto_price}")
                if crypto_price:
                    conversion_rate = 1 / crypto_price
            
            # Fiat to Fiat
            elif from_type == 'fiat' and to_type == 'fiat':
                logger.info(f"Fiat to fiat conversion: {from_normalized} -> {to_normalized}")
                conversion_rate = await self.get_fiat_rate(from_normalized, to_normalized)
                logger.info(f"Conversion rate: {conversion_rate}")
            
            if conversion_rate is None:
                logger.error(f"Failed to get conversion rate for {from_curr} to {to_curr}")
                return None
            
            converted_amount = amount * conversion_rate
            
            return {
                'original_amount': amount,
                'converted_amount': converted_amount,
                'from_currency': from_curr.upper(),
                'to_currency': to_curr.upper(),
                'rate': conversion_rate,
                'from_type': from_type,
                'to_type': to_type
            }
            
        except Exception as e:
            logger.error(f"Error in currency conversion: {e}")
            return None

    def format_conversion_result(self, result: dict) -> str:
        """Format the conversion result into a professional message"""
        try:
            original = result['original_amount']
            converted = result['converted_amount']
            from_curr = result['from_currency']
            to_curr = result['to_currency']
            rate = result['rate']
            
            # Format numbers appropriately
            if converted >= 1:
                converted_str = f"{converted:,.2f}"
            else:
                converted_str = f"{converted:.8f}".rstrip('0').rstrip('.')
            
            if rate >= 1:
                rate_str = f"{rate:,.2f}"
            else:
                rate_str = f"{rate:.8f}".rstrip('0').rstrip('.')
            
            original_str = f"{original:,.2f}" if original >= 1 else f"{original:.8f}".rstrip('0').rstrip('.')
            
            # Create professional response
            response = f"""
**💱 CURRENCY CONVERSION**

**{original_str} {from_curr}** = **{converted_str} {to_curr}**

📊 **Exchange Rate:**
**1 {from_curr} = {rate_str} {to_curr}**
            """.strip()
            
            return response
            
        except Exception as e:
            logger.error(f"Error formatting conversion result: {e}")
            return "❌ **Error formatting conversion result**"

# Initialize converter instance
converter = CurrencyConverter()

async def handle_conversion_command(event):
    """Handle the /conv command for currency conversion"""
    try:
        message_text = event.message.message
        
        # Parse the conversion command
        parsed = converter.parse_conversion_command(message_text)
        
        if not parsed:
            await event.reply(
                "❌ **Invalid Format**\n\n"
                "📝 **Usage Examples:**\n"
                "• `/conv 1600 ngn usd`\n"
                "• `/conv 1600ngn usd`\n"
                "• `/conv 0.5 btc eth`\n"
                "• `/conv 100 usd` (converts to USD by default)\n\n"
                "💡 **Supported:** Crypto ↔ Crypto, Crypto ↔ Fiat, Fiat ↔ Fiat"
            )
            return
        
        amount, from_curr, to_curr = parsed
        
        # Show processing message
        processing_msg = await event.reply("🔄 **Converting...** Please wait")
        
        # Perform conversion
        result = await converter.convert_currency(amount, from_curr, to_curr)
        
        if result:
            # Format and send result
            formatted_result = converter.format_conversion_result(result)
            await processing_msg.edit(formatted_result)
        else:
            await processing_msg.edit(
                "❌ **Conversion Failed**\n\n"
                "🔍 **Possible Issues:**\n"
                "• Invalid currency ticker\n"
                "• Currency not supported\n"
                "• API temporarily unavailable\n\n"
                "💡 **Tip:** Check spelling and try again"
            )
            logger.error(f"Conversion failed for: {amount} {from_curr} to {to_curr}")
            
    except Exception as e:
        logger.error(f"Error handling conversion command: {e}")
        await event.reply(
            "⚠️ **Unexpected Error**\n\n"
            "❌ Something went wrong during conversion\n"
            "🔄 Please try again in a moment"
        )

__all__ = ['handle_conversion_command', 'converter']