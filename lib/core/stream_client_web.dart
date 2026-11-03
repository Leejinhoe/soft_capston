import 'package:fetch_client/fetch_client.dart';
import 'package:http/http.dart' as http;

http.Client createStreamingClient() => FetchClient(mode: RequestMode.cors);
